#!/usr/bin/env python3
"""sprite-canvas: place sprites onto a fixed canvas size with an anchor (center, feet /
bottom, top-left, ...). Images smaller than the canvas are padded; larger ones are cropped
unless `--fit` (scale down to fit) is set. `--upscale` with `--fit` also allows scaling
up. `--bg` is an optional #RRGGBB or #RRGGBBAA background (default transparent). Writes a
new directory of PNGs; inputs are never overwritten unless `--in-place`.
"""
import argparse, os, json, re, sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

IMAGE_EXTS = {".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def parse_size(s):
    m = re.match(r"^\s*(\d+)\s*[xX,]\s*(\d+)\s*$", s or "")
    if not m:
        raise SystemExit("--size expects WxH (e.g. 64x64)")
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        raise SystemExit("--size must be positive")
    return w, h


def parse_color(s):
    if not s:
        return (0, 0, 0, 0)
    t = s.strip().lstrip("#")
    if len(t) == 6:
        r, g, b = int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
        return (r, g, b, 255)
    if len(t) == 8:
        r, g, b, a = int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16), int(t[6:8], 16)
        return (r, g, b, a)
    raise SystemExit("--bg expects #RRGGBB or #RRGGBBAA")


def anchor_xy(cw, ch, w, h, anchor):
    a = (anchor or "center").lower().replace("_", "-")
    table = {
        "top-left": (0, 0), "nw": (0, 0), "origin": (0, 0),
        "top": ((cw - w) // 2, 0), "top-center": ((cw - w) // 2, 0), "n": ((cw - w) // 2, 0),
        "top-right": (cw - w, 0), "ne": (cw - w, 0),
        "left": (0, (ch - h) // 2), "w": (0, (ch - h) // 2),
        "center": ((cw - w) // 2, (ch - h) // 2), "centre": ((cw - w) // 2, (ch - h) // 2),
        "middle": ((cw - w) // 2, (ch - h) // 2),
        "right": (cw - w, (ch - h) // 2), "e": (cw - w, (ch - h) // 2),
        "bottom-left": (0, ch - h), "sw": (0, ch - h),
        "bottom": ((cw - w) // 2, ch - h), "bottom-center": ((cw - w) // 2, ch - h),
        "feet": ((cw - w) // 2, ch - h), "s": ((cw - w) // 2, ch - h),
        "bottom-right": (cw - w, ch - h), "se": (cw - w, ch - h),
    }
    if a not in table:
        raise SystemExit(f"unknown --anchor {anchor}")
    return table[a]


def place(im, cw, ch, anchor, bg, fit, upscale):
    im = im.convert("RGBA")
    w, h = im.size
    if fit and (w > cw or h > ch or (upscale and (w < cw and h < ch))):
        scale = min(cw / w, ch / h)
        if scale < 1 or upscale:
            nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
            im = im.resize((nw, nh), Image.Resampling.NEAREST)
            w, h = im.size
    canvas = Image.new("RGBA", (cw, ch), bg)
    x, y = anchor_xy(cw, ch, w, h, anchor)
    # crop when the sprite hangs off the canvas (no --fit, or after rounding)
    src_x = 0 if x >= 0 else -x
    src_y = 0 if y >= 0 else -y
    dst_x, dst_y = max(x, 0), max(y, 0)
    if src_x < w and src_y < h and dst_x < cw and dst_y < ch:
        box = (src_x, src_y, min(w, src_x + (cw - dst_x)), min(h, src_y + (ch - dst_y)))
        canvas.alpha_composite(im.crop(box), (dst_x, dst_y))
    return canvas


def collect(inputs):
    files = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(q for q in p.iterdir() if q.is_file() and q.suffix.lower() in IMAGE_EXTS))
        elif p.is_file():
            files.append(p)
        else:
            raise SystemExit(f"not found: {raw}")
    if not files:
        raise SystemExit("no images found")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Place sprites onto a fixed canvas with an anchor.")
    ap.add_argument("input", nargs="+", help="image files or folders")
    ap.add_argument("-o", "--out", required=True, help="output folder")
    ap.add_argument("--size", required=True, help="WxH canvas size")
    ap.add_argument("--anchor", default="center")
    ap.add_argument("--bg", default=None, help="#RRGGBB or #RRGGBBAA (default transparent)")
    ap.add_argument("--fit", action="store_true", help="scale down (NEAREST) to fit the canvas")
    ap.add_argument("--upscale", action="store_true", help="with --fit, also scale smaller images up")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    cw, ch = parse_size(a.size)
    bg = parse_color(a.bg)
    files = collect(a.input)
    if a.json:
        safe_out.check_any([str(s) for s in files], a.json, a.in_place)
    os.makedirs(a.out, exist_ok=True)
    written = []
    for src in files:
        dest = os.path.join(a.out, src.stem + ".png")
        safe_out.check(str(src), dest, a.in_place)
        im = Image.open(src)
        out = place(im, cw, ch, a.anchor, bg, a.fit, a.upscale)
        out.save(dest)
        written.append({"src": str(src), "path": dest, "src_size": list(im.size)})
    rec = {"count": len(written), "size": [cw, ch], "anchor": a.anchor, "out": a.out, "files": written}
    print(f"{len(written)} image(s) at {cw}x{ch} -> {a.out}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
