"""Hand-made image features (numpy + Pillow only, no learned weights)."""
import io
import numpy as np
from PIL import Image, ImageFilter

FEATURE_VERSION = 2  # bump when any feature definition changes (part of the cache key)
HIST_BINS = 8  # per channel -> 512-bin joint RGB histogram


def _dct_mat(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2.0 / n)
    m[0] /= np.sqrt(2.0)
    return m


_D32 = _dct_mat(32)


def to_rgb(img):
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(bg, img)
    return img.convert("RGB")


def colour_hist(img, bins=HIST_BINS):
    a = np.asarray(img.resize((64, 64), Image.BILINEAR), dtype=np.uint8).reshape(-1, 3)
    q = (a.astype(np.int32) * bins) // 256
    idx = q[:, 0] * bins * bins + q[:, 1] * bins + q[:, 2]
    h = np.bincount(idx, minlength=bins ** 3).astype(np.float32)
    return h / h.sum()


def phash(img):
    """64-bit DCT perceptual hash (pHash-style): 32x32 grey, DCT, top-left 8x8 minus DC, median threshold."""
    g = np.asarray(img.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float64)
    d = _D32 @ g @ _D32.T
    low = d[:8, :8].flatten()
    med = np.median(low[1:])
    return np.packbits(low > med)  # 8 bytes


def dhash(img):
    g = np.asarray(img.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.int16)
    return np.packbits((g[:, 1:] > g[:, :-1]).flatten())


def simple_feats(img):
    """Small fixed feature vector for the linear baseline: 4x4 RGB thumb, grey 8x8 thumb,
    gradient-energy stats, colour moments, distinct-colour count (pixel-art cue)."""
    s = img.resize((64, 64), Image.BILINEAR)
    a = np.asarray(s, dtype=np.float32) / 255.0
    thumb = np.asarray(img.resize((4, 4), Image.BOX), dtype=np.float32).flatten() / 255.0
    grey = np.asarray(img.convert("L").resize((8, 8), Image.BOX), dtype=np.float32).flatten() / 255.0
    gy = np.abs(np.diff(a.mean(2), axis=0))
    gx = np.abs(np.diff(a.mean(2), axis=1))
    grad = np.array([gx.mean(), gy.mean(), (gx > 0.1).mean(), (gy > 0.1).mean(), (gx == 0).mean(), (gy == 0).mean()], np.float32)
    flat = a.reshape(-1, 3)
    mom = np.concatenate([flat.mean(0), flat.std(0)])
    hsv = np.asarray(s.convert("HSV"), dtype=np.float32).reshape(-1, 3) / 255.0
    hmom = np.concatenate([hsv.mean(0), hsv.std(0)])
    small = np.asarray(img.resize((32, 32), Image.NEAREST)).reshape(-1, 3)
    ncol = len(np.unique(small[:, 0].astype(np.int32) * 65536 + small[:, 1].astype(np.int32) * 256 + small[:, 2]))
    aspect = np.array([np.log(img.size[0] / max(1, img.size[1])), np.log(ncol) / np.log(1024)], np.float32)
    return np.concatenate([thumb, grey, grad, mom, hmom, aspect]).astype(np.float32)


SIMPLE_DIM = 48 + 64 + 6 + 6 + 6 + 2


def all_feats(img):
    img = to_rgb(img)
    return colour_hist(img), phash(img), dhash(img), simple_feats(img)


def open_image(path, max_side=512):
    img = Image.open(path)
    if img.format == "JPEG":
        img.draft("RGB", (max_side, max_side))
    img.load()
    return img


def augment(img, kind, seed=0, quality=40):
    """Deterministic perturbations for the near-duplicate retrieval task."""
    img = to_rgb(img)
    w, h = img.size
    if kind == "rescale":
        return img.resize((max(8, w // 2), max(8, h // 2)), Image.BILINEAR)
    if kind == "jpeg":
        b = io.BytesIO()
        img.save(b, "JPEG", quality=40)
        b.seek(0)
        return Image.open(b).convert("RGB")
    if kind == "bright":
        a = np.asarray(img, dtype=np.float32) * 1.25 + 10
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if kind == "crop":
        dx, dy = int(w * 0.05), int(h * 0.05)
        return img.crop((dx, dy, w - dx, h - dy))
    # ---- hard tier ----
    if kind == "h_rescale":
        return img.resize((max(8, w // 4), max(8, h // 4)), Image.BILINEAR)
    if kind == "h_jpeg":
        return augment(img, "jpeg_q", seed, quality=10)
    if kind == "h_colour":  # colour cast + brightness shift, per-channel gains
        a = np.asarray(img, dtype=np.float32) * np.array([1.3, 0.8, 1.1], np.float32) + 25
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if kind == "h_crop":  # 15% off each side -> 49% of the area left
        dx, dy = int(w * 0.15), int(h * 0.15)
        return img.crop((dx, dy, max(dx + 8, w - dx), max(dy + 8, h - dy)))
    if kind == "h_noise":  # blur + gaussian noise, noise seeded from the caller's seed
        from PIL import ImageFilter
        b = img.filter(ImageFilter.GaussianBlur(1.5))
        a = np.asarray(b, dtype=np.float32) + np.random.default_rng(seed).normal(0, 12, (b.size[1], b.size[0], 3)).astype(np.float32)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if kind == "h_combo":  # crop 10% + half size + JPEG q25 + brightness
        dx, dy = int(w * 0.10), int(h * 0.10)
        c = img.crop((dx, dy, max(dx + 8, w - dx), max(dy + 8, h - dy)))
        c = c.resize((max(8, c.size[0] // 2), max(8, c.size[1] // 2)), Image.BILINEAR)
        c = augment(c, "jpeg_q", seed, quality=25)
        a = np.asarray(c, dtype=np.float32) * 1.2 + 15
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    if kind == "jpeg_q":
        b = io.BytesIO()
        img.save(b, "JPEG", quality=quality)
        b.seek(0)
        return Image.open(b).convert("RGB")
    raise ValueError(kind)


AUG_KINDS = ("rescale", "jpeg", "bright", "crop")  # mild tier (unchanged since v1)
HARD_KINDS = ("h_rescale", "h_jpeg", "h_colour", "h_crop", "h_noise", "h_combo")
TIERS = {"mild": AUG_KINDS, "hard": HARD_KINDS}
TIER_OF = {k: t for t, ks in TIERS.items() for k in ks}
NORM_SIZE = 256
NORM_MODES = ("letterbox", "stretch")
RESAMPLE = {"lanczos": Image.LANCZOS, "bicubic": Image.BICUBIC, "bilinear": Image.BILINEAR, "nearest": Image.NEAREST}

# Named T1/T6 protocols. "letterbox" / "stretch" are the v1.1–v1.2 defaults (no bottleneck).
# Anti-leak variants send every frame through a shared low-resolution bottleneck, then back up to 256
# with the same resample filter, optionally with a mild blur or JPEG round-trip at the bottleneck.
PROTOCOLS = {
    "letterbox": {"mode": "letterbox", "size": NORM_SIZE},
    "stretch": {"mode": "stretch", "size": NORM_SIZE},
    "bn64": {"mode": "letterbox", "size": NORM_SIZE, "bottleneck": 64, "resample": "lanczos"},
    "bn96": {"mode": "letterbox", "size": NORM_SIZE, "bottleneck": 96, "resample": "lanczos"},
    "bn64_blur": {"mode": "letterbox", "size": NORM_SIZE, "bottleneck": 64, "resample": "lanczos", "blur": 1.0},
    "bn64_jpeg": {"mode": "letterbox", "size": NORM_SIZE, "bottleneck": 64, "resample": "lanczos", "jpeg": 50},
}
# Official T1 protocol after the v1.3 measured comparison (see BENCHMARK_CARD.md).
OFFICIAL_T1_PROTOCOL = "bn64"
ANTILEAK_PROTOCOLS = ("bn64", "bn96", "bn64_blur", "bn64_jpeg")


def resolve_protocol(norm):
    """Accept a protocol name, a mode string, or a dict; return a canonical dict."""
    if norm is None:
        return None
    if isinstance(norm, str):
        if norm in PROTOCOLS:
            p = dict(PROTOCOLS[norm])
            p["name"] = norm
            return canonical_protocol(p)
        raise ValueError(f"unknown norm protocol {norm!r}")
    return canonical_protocol(dict(norm))


def canonical_protocol(p):
    mode = p.get("mode", "letterbox")
    if mode not in NORM_MODES:
        raise ValueError(mode)
    out = {"mode": mode, "size": int(p.get("size", NORM_SIZE))}
    if p.get("name"):
        out["name"] = p["name"]
    if p.get("bottleneck"):
        out["bottleneck"] = int(p["bottleneck"])
        out["resample"] = p.get("resample") or "lanczos"
        if out["resample"] not in RESAMPLE:
            raise ValueError(out["resample"])
    if p.get("blur"):
        out["blur"] = float(p["blur"])
    if p.get("jpeg"):
        out["jpeg"] = int(p["jpeg"])
    return out


def protocol_with_mode(norm, mode):
    p = resolve_protocol(norm)
    p["mode"] = mode
    if p.get("name"):
        # keep extras; name becomes e.g. bn64@stretch for logs
        p["name"] = f"{p['name']}@{mode}" if not p["name"].endswith(f"@{mode}") and p["name"] not in NORM_MODES else mode
    return canonical_protocol(p)


def is_legacy_protocol(p):
    """True for the v1.1/v1.2 letterbox/stretch-to-256 path (existing feature caches)."""
    if not p:
        return False
    p = resolve_protocol(p)
    extras = {k: v for k, v in p.items() if k not in ("mode", "size", "name")}
    return p.get("size", NORM_SIZE) == NORM_SIZE and not extras


def cache_norm_token(norm):
    """Value stored in the frame-cache key. Legacy letterbox/stretch keep the v1.1 token."""
    if not norm:
        return None
    p = resolve_protocol(norm)
    if is_legacy_protocol(p):
        return [p["mode"], p["size"]]
    # exclude 'name' so equivalent dicts share a cache
    return {k: v for k, v in p.items() if k != "name"}


def jpeg_roundtrip(img, quality):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=int(quality))
    b.seek(0)
    return Image.open(b).convert("RGB")


def _square(img, size, mode, filt_down, filt_up):
    w, h = img.size
    if mode == "stretch":
        return img.resize((size, size), filt_down if max(w, h) > size else filt_up)
    s = size / max(w, h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    r = img.resize((nw, nh), filt_down if s < 1 else filt_up)
    canvas = Image.new("RGB", (size, size), (0, 0, 0))
    canvas.paste(r, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def normalise(img, size=NORM_SIZE, mode="letterbox", bottleneck=None, blur=None, jpeg=None, resample="lanczos"):
    """Resize every frame to size x size before features, so pixel dimensions and aspect carry no signal.
    letterbox: keep aspect, scale longest side to the current canvas, centre on black (padding bars still reveal aspect ratio).
    stretch: ignore aspect, resize straight to canvas x canvas (no bars, content is distorted).

    With bottleneck=N, every frame (including those already smaller than N) is first placed on an N x N
    canvas with the same mode, optionally blurred and/or JPEG-compressed, then resampled up to size x size
    with the same filter. That shared low-resolution hop is what v1.3 uses to cut native-scale traces.
    With no bottleneck/blur/jpeg, pixels match the v1.1–v1.2 path (LANCZOS down, BICUBIC up)."""
    if mode not in NORM_MODES:
        raise ValueError(mode)
    img = to_rgb(img)
    if not bottleneck and not blur and not jpeg:
        # v1.1 / v1.2 path, bit-identical
        return _square(img, size, mode, Image.LANCZOS, Image.BICUBIC)
    filt = RESAMPLE[resample if resample in RESAMPLE else "lanczos"]
    mid_size = int(bottleneck) if bottleneck else size
    mid = _square(img, mid_size, mode, filt, filt)
    if blur:
        mid = mid.filter(ImageFilter.GaussianBlur(radius=float(blur)))
    if jpeg:
        mid = jpeg_roundtrip(mid, jpeg)
    if mid.size != (size, size):
        mid = mid.resize((size, size), filt)
    return mid


def apply_norm(img, norm):
    """Apply a named or dict protocol (used by the extractor)."""
    p = resolve_protocol(norm)
    return normalise(img, size=p.get("size", NORM_SIZE), mode=p["mode"],
                     bottleneck=p.get("bottleneck"), blur=p.get("blur"),
                     jpeg=p.get("jpeg"), resample=p.get("resample", "lanczos"))
