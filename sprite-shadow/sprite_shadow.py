#!/usr/bin/env python3
"""sprite-shadow: add a shadow to sprites or animation frames. Modes:
  drop     the sprite's own silhouette, offset (--dx/--dy), blurred (--blur), tinted (--color) at --opacity;
  contact  a soft ellipse under the sprite's feet: width from the opaque bounding box (--width-scale), height --squash of that width,
           centred on the bottom of the box (+ --dy), so characters stand on the ground instead of floating.
The canvas grows so nothing is cut off. With several frames the SAME padding is used for all of them, so every output frame keeps one
size and the sprite does not jitter (the contact ellipse follows each frame's own feet). --keep-size crops back to the input size instead.
"""
import argparse, os, glob, sys

import numpy as np
from PIL import Image, ImageFilter


def parse_color(s):
    s = s.lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def shadow_layer(im, mode, dx, dy, blur, width_scale, squash):
    a = im.getchannel("A")
    if mode == "drop":
        sh = Image.new("L", im.size, 0); sh.paste(a, (dx, dy)); return sh if blur <= 0 else sh.filter(ImageFilter.GaussianBlur(blur))
    bbox = a.getbbox(); sh = Image.new("L", im.size, 0)
    if bbox:
        x0, y0, x1, y1 = bbox; cx = (x0 + x1) / 2; w = (x1 - x0) * width_scale; h = max(1.0, w * squash); cy = y1 + dy
        yy, xx = np.mgrid[0:im.height, 0:im.width]; d = ((xx + 0.5 - cx - dx) / (w / 2)) ** 2 + ((yy + 0.5 - cy) / (h / 2)) ** 2
        sh = Image.fromarray((np.clip(1.0 - d, 0, 1) * 255).astype(np.uint8), "L") if blur > 0 else Image.fromarray(((d <= 1) * 255).astype(np.uint8), "L")
    return sh if blur <= 0 else sh.filter(ImageFilter.GaussianBlur(blur))


def pad_for(mode, ims, dx, dy, blur, width_scale, squash):
    """Padding (left, top, right, bottom) big enough for every frame."""
    r = int(np.ceil(blur * 3)); L = T = R = B = 0
    for im in ims:
        bbox = im.getchannel("A").getbbox()
        if mode == "drop":
            L = max(L, r - dx); R = max(R, r + dx); T = max(T, r - dy); B = max(B, r + dy)
        elif bbox:
            x0, y0, x1, y1 = bbox; w = (x1 - x0) * width_scale; h = max(1.0, w * squash); cx = (x0 + x1) / 2 + dx; cy = y1 + dy
            L = max(L, int(np.ceil(w / 2 - cx)) + r); R = max(R, int(np.ceil(cx + w / 2 - im.width)) + r)
            T = max(T, int(np.ceil(h / 2 - cy)) + r); B = max(B, int(np.ceil(cy + h / 2 - im.height)) + r)
    return max(L, 0), max(T, 0), max(R, 0), max(B, 0)


def add_shadow(ims, mode="drop", dx=2, dy=2, blur=1.0, opacity=0.5, color="#000000", width_scale=0.9, squash=0.3, keep_size=False):
    ims = [i.convert("RGBA") for i in ims]; col = parse_color(color) if isinstance(color, str) else color
    L, T, R, B = pad_for(mode, ims, dx, dy, blur, width_scale, squash); out = []
    for im in ims:
        canvas = Image.new("RGBA", (im.width + L + R, im.height + T + B), (0, 0, 0, 0)); canvas.paste(im, (L, T))
        sh = shadow_layer(canvas, mode, dx, dy, blur, width_scale, squash)
        layer = Image.new("RGBA", canvas.size, col + (0,)); layer.putalpha(sh.point(lambda v: int(round(v * opacity))))
        res = Image.alpha_composite(layer, canvas)
        out.append(res.crop((L, T, L + im.width, T + im.height)) if keep_size else res)
    return out, (L, T, R, B)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add drop or contact shadows to sprites.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs or folders"); ap.add_argument("-o", "--out", required=True, help="output folder (or file for one input)")
    ap.add_argument("--mode", choices=["drop", "contact"], default="drop"); ap.add_argument("--dx", type=int, default=2); ap.add_argument("--dy", type=int, default=2)
    ap.add_argument("--blur", type=float, default=1.0); ap.add_argument("--opacity", type=float, default=0.5); ap.add_argument("--color", default="#000000")
    ap.add_argument("--width-scale", type=float, default=0.9); ap.add_argument("--squash", type=float, default=0.3); ap.add_argument("--keep-size", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = []
    for p in a.inputs: files += sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else (sorted(glob.glob(p)) or [p])
    if not files: sys.exit("no input images")
    missing = [f for f in files if not os.path.exists(f)]
    if missing: sys.exit(f"not found: {missing[0]}")
    ims, pad = add_shadow([Image.open(f) for f in files], a.mode, a.dx, a.dy, a.blur, a.opacity, a.color, a.width_scale, a.squash, a.keep_size)
    single = len(files) == 1 and os.path.splitext(a.out)[1].lower() == ".png"
    if not single: os.makedirs(a.out, exist_ok=True)
    for f, im in zip(files, ims):
        dest = a.out if single else os.path.join(a.out, os.path.basename(f))
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
        im.save(dest)
    print(f"{len(files)} image(s), {a.mode} shadow; padding added (left, top, right, bottom) = {pad if not a.keep_size else 'none (--keep-size)'} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
