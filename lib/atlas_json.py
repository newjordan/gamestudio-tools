"""Load and rewrite TexturePacker / atlas-pack JSON (hash or array `frames`).

Used by sprite-rotate, sprite-scale and sprite-pad when an atlas is given.
Rotated packed frames (`rotated: true`) are refused. Coordinates are integer.
"""
import json, os, sys

from gst_errors import GstInputError
import gst_read


def load(path):
    data = gst_read.require_object(gst_read.load_json(path, "atlas JSON"), "atlas JSON")
    frames = data.get("frames")
    if frames is None:
        raise GstInputError("%s: atlas JSON has no frames" % path)
    if isinstance(frames, list):
        items = [(f.get("filename") or f.get("name") or f.get("id") or str(i), f)
                 for i, f in enumerate(frames)]
        kind = "array"
    else:
        items = list(frames.items())
        kind = "hash"
    return data, items, kind


def image_name(data, atlas_path=None):
    meta = data.get("meta") or {}
    name = meta.get("image") or meta.get("texture")
    if name:
        return name
    if atlas_path:
        return os.path.splitext(os.path.basename(atlas_path))[0] + ".png"
    return None


def image_path(atlas_path, data, explicit=None):
    if explicit:
        return explicit
    name = image_name(data, atlas_path)
    if not name:
        raise GstInputError(f"{atlas_path}: atlas meta.image is missing")
    return os.path.join(os.path.dirname(os.path.abspath(atlas_path)), name)


def has_rotated(items):
    return any(bool(rec.get("rotated")) for _, rec in items)


def frame_xywh(rec):
    fr = rec.get("frame") or rec
    try:
        return [int(fr["x"]), int(fr["y"]), int(fr["w"]), int(fr["h"])]
    except KeyError:
        raise GstInputError("atlas frame is missing x/y/w/h")


def source_size(rec):
    ss = rec.get("sourceSize") or {}
    if "w" in ss and "h" in ss:
        return int(ss["w"]), int(ss["h"])
    _x, _y, w, h = frame_xywh(rec)
    return w, h


def sprite_source(rec):
    sss = rec.get("spriteSourceSize") or {}
    if "w" in sss:
        return [int(sss.get("x") or 0), int(sss.get("y") or 0), int(sss["w"]), int(sss["h"])]
    x, y, w, h = frame_xywh(rec)
    return [0, 0, w, h]


def set_xywh(rec, x, y, w, h):
    out = json.loads(json.dumps(rec))
    if "frame" in out:
        out["frame"] = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
    else:
        out["x"], out["y"], out["w"], out["h"] = int(x), int(y), int(w), int(h)
    return out


def set_sizes(rec, src_w, src_h, sx, sy, sw, sh):
    out = rec
    if "sourceSize" in out or "spriteSourceSize" in out or "frame" in out:
        out["sourceSize"] = {"w": int(src_w), "h": int(src_h)}
        out["spriteSourceSize"] = {"x": int(sx), "y": int(sy), "w": int(sw), "h": int(sh)}
        trimmed = not (sx == 0 and sy == 0 and sw == src_w and sh == src_h)
        if "trimmed" in out or "frame" in out:
            out["trimmed"] = trimmed
    return out


def rotate_rect(x, y, w, h, sheet_w, sheet_h, angle):
    """CCW 90/180/270. `angle` already normalised to those values."""
    if angle == 90:
        return y, sheet_w - x - w, h, w
    if angle == 180:
        return sheet_w - x - w, sheet_h - y - h, w, h
    if angle == 270:
        return sheet_h - y - h, x, h, w
    return x, y, w, h


def rotate_source(sx, sy, sw, sh, src_w, src_h, angle):
    if angle == 90:
        return sy, src_w - sx - sw, sh, sw, src_h, src_w
    if angle == 180:
        return src_w - sx - sw, src_h - sy - sh, sw, sh, src_w, src_h
    if angle == 270:
        return src_h - sy - sh, sx, sh, sw, src_h, src_w
    return sx, sy, sw, sh, src_w, src_h


def new_sheet_size(w, h, angle):
    if angle in (90, 270):
        return h, w
    return w, h


def exact_angle(angle):
    a = angle % 360
    for cand in (0, 90, 180, 270):
        dist = min((a - cand) % 360, (cand - a) % 360)
        if dist < 1e-9:
            return cand
    return None


def rewrite_rotate(data, items, angle, sheet_w, sheet_h):
    if has_rotated(items):
        raise GstInputError("rotated atlas frames are refused; unpack first, then rotate")
    ang = exact_angle(angle)
    if ang is None:
        raise GstInputError("packed atlas rewrite needs a 90/180/270 degree angle (unpack for arbitrary angles)")
    nw, nh = new_sheet_size(sheet_w, sheet_h, ang)
    new_items = []
    for name, rec in items:
        x, y, w, h = frame_xywh(rec)
        nx, ny, nw_, nh_ = rotate_rect(x, y, w, h, sheet_w, sheet_h, ang)
        out = set_xywh(rec, nx, ny, nw_, nh_)
        sx, sy, sw, sh = sprite_source(rec)
        src_w, src_h = source_size(rec)
        nsx, nsy, nsw, nsh, nsrc_w, nsrc_h = rotate_source(sx, sy, sw, sh, src_w, src_h, ang)
        out = set_sizes(out, nsrc_w, nsrc_h, nsx, nsy, nsw, nsh)
        new_items.append((name, out))
    return _store(data, new_items, nw, nh)


def _scale_i(v, s, min_one=False):
    n = int(round(v * s))
    if min_one:
        return max(1, n)
    return n


def rewrite_scale(data, items, sx, sy, sheet_w, sheet_h):
    if has_rotated(items):
        raise GstInputError("rotated atlas frames are refused; unpack first, then scale")
    if sx <= 0 or sy <= 0:
        raise GstInputError("scale must be > 0")
    new_items = []
    for name, rec in items:
        x, y, w, h = frame_xywh(rec)
        out = set_xywh(rec, _scale_i(x, sx), _scale_i(y, sy),
                       _scale_i(w, sx, True), _scale_i(h, sy, True))
        ssx, ssy, ssw, ssh = sprite_source(rec)
        src_w, src_h = source_size(rec)
        out = set_sizes(out,
                        _scale_i(src_w, sx, True), _scale_i(src_h, sy, True),
                        _scale_i(ssx, sx), _scale_i(ssy, sy),
                        _scale_i(ssw, sx, True), _scale_i(ssh, sy, True))
        new_items.append((name, out))
    return _store(data, new_items, _scale_i(sheet_w, sx, True), _scale_i(sheet_h, sy, True))


def rewrite_pad(data, items, left, top, right, bottom, sheet_w, sheet_h):
    """Grow each sprite's source canvas (trim offsets move by left/top). Packed
    frame rects are left as-is — this is for per-sprite pads, not sheet packing."""
    new_items = []
    for name, rec in items:
        x, y, w, h = frame_xywh(rec)
        out = set_xywh(rec, x, y, w, h)
        ssx, ssy, ssw, ssh = sprite_source(rec)
        src_w, src_h = source_size(rec)
        out = set_sizes(out, src_w + left + right, src_h + top + bottom,
                        ssx + left, ssy + top, ssw, ssh)
        new_items.append((name, out))
    return _store(data, new_items, sheet_w, sheet_h)


def rewrite_unpad(data, items, left, top, right, bottom, sheet_w, sheet_h):
    """Shrink each sprite's source canvas (the inverse of rewrite_pad). Packed
    frame rects are left as-is. Refuses to clip packed content or shrink a
    sourceSize below 1x1.
    """
    new_items = []
    for name, rec in items:
        x, y, w, h = frame_xywh(rec)
        out = set_xywh(rec, x, y, w, h)
        ssx, ssy, ssw, ssh = sprite_source(rec)
        src_w, src_h = source_size(rec)
        nw, nh = src_w - left - right, src_h - top - bottom
        if nw < 1 or nh < 1:
            raise GstInputError(f"unpad would shrink {name!r} sourceSize below 1x1")
        nsx, nsy = ssx - left, ssy - top
        if nsx < 0 or nsy < 0 or nsx + ssw > nw or nsy + ssh > nh:
            raise GstInputError(f"unpad would clip packed content of {name!r}")
        out = set_sizes(out, nw, nh, nsx, nsy, ssw, ssh)
        new_items.append((name, out))
    return _store(data, new_items, sheet_w, sheet_h)


def _store(data, items, sheet_w, sheet_h):
    out = json.loads(json.dumps(data))
    if isinstance(data.get("frames"), list):
        out["frames"] = [rec if "filename" in rec or "name" in rec or "id" in rec
                         else dict(rec, filename=name) if False else rec
                         for name, rec in items]
        # keep original key style: write the rewritten records in order
        out["frames"] = [rec for _n, rec in items]
    else:
        out["frames"] = {name: rec for name, rec in items}
    meta = dict(out.get("meta") or {})
    if "size" in meta or "image" in meta:
        meta["size"] = {"w": int(sheet_w), "h": int(sheet_h)}
        out["meta"] = meta
    return out, items, sheet_w, sheet_h


def save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    json.dump(data, open(path, "w"), indent=2)


def default_atlas_out(image_out, atlas_in):
    root, _ = os.path.splitext(image_out)
    # keep .json even if image_out is a directory handled by the caller
    ext = os.path.splitext(atlas_in)[1] or ".json"
    return root + ext
