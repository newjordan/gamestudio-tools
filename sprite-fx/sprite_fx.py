#!/usr/bin/env python3
"""sprite-fx: bake outline, drop shadow and hit-flash variants into sprites or whole frame folders.

Every output in a run is padded by the same amount so animation frames keep their alignment.
--outline N (px, 4- or 8-neighbour), --shadow DX,DY[,ALPHA[,BLUR]], --flash (adds *_flash.png, sprite
tinted toward white), --flash-amount 0..1.
"""
import argparse, glob, os
import numpy as np
from PIL import Image, ImageFilter
import os, sys


def grow(mask, n, eight=True):
    m = mask.copy()
    for _ in range(n):
        g = m.copy()
        g[1:, :] |= m[:-1, :]; g[:-1, :] |= m[1:, :]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
        if eight:
            g[1:, 1:] |= m[:-1, :-1]; g[1:, :-1] |= m[:-1, 1:]; g[:-1, 1:] |= m[1:, :-1]; g[:-1, :-1] |= m[1:, 1:]
        m = g
    return m


def pad_for(outline, shadow):
    dx, dy, _, blur = shadow if shadow else (0, 0, 0, 0)
    return outline + max(abs(dx), abs(dy)) + int(blur * 2)


def bake(img, outline=0, outline_color=(0, 0, 0, 255), shadow=None, pad=None, eight=True):
    img = img.convert("RGBA")
    pad = pad_for(outline, shadow) if pad is None else pad
    canvas = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    canvas.paste(img, (pad, pad))
    arr = np.array(canvas)
    solid = arr[..., 3] > 0
    layers = []
    if shadow:
        dx, dy, alpha, blur = shadow
        sh = Image.fromarray((np.roll(np.roll(solid, dy, 0), dx, 1) * int(255 * alpha)).astype(np.uint8), "L")
        if blur:
            sh = sh.filter(ImageFilter.GaussianBlur(blur))
        s = Image.new("RGBA", canvas.size, (0, 0, 0, 255))
        s.putalpha(sh)
        layers.append(s)
    if outline:
        edge = grow(solid, outline, eight) & ~solid
        o = np.zeros_like(arr)
        o[edge] = outline_color
        layers.append(Image.fromarray(o, "RGBA"))
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    for l in layers:
        out = Image.alpha_composite(out, l)
    return Image.alpha_composite(out, canvas)


def flash(img, amount=0.85, color=(255, 255, 255)):
    a = np.array(img.convert("RGBA")).astype(np.float32)
    a[..., :3] = a[..., :3] * (1 - amount) + np.array(color, np.float32) * amount
    return Image.fromarray(a.round().astype(np.uint8), "RGBA")


def parse_color(s):
    """#rrggbb, #rrggbbaa, or the same without a hash. Matches sprite-outline-gen."""
    s = str(s).lstrip("#")
    if len(s) == 6:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    if len(s) == 8:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
    raise SystemExit("colour %r must be #rrggbb or #rrggbbaa" % s)


def parse_shadow(s):
    if not s:
        return None
    p = [float(x) for x in s.split(",")]
    dx, dy = int(p[0]), int(p[1])
    alpha = p[2] if len(p) > 2 else 0.5
    blur = p[3] if len(p) > 3 else 0
    return (dx, dy, alpha, blur)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake outline / shadow / flash into sprites.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs, or directories")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--outline", type=int, default=0)
    ap.add_argument("--outline-color", default="000000")
    ap.add_argument("--four", action="store_true", help="4-neighbour outline (no diagonals)")
    ap.add_argument("--shadow", help="DX,DY[,ALPHA[,BLUR]]  e.g. 2,2,0.5,1")
    ap.add_argument("--flash", action="store_true")
    ap.add_argument("--flash-amount", type=float, default=0.85)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = []
    for p in a.inputs:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "*.png")))
        else:
            files += sorted(glob.glob(p)) or [p]
    os.makedirs(a.outdir, exist_ok=True)
    sh = parse_shadow(a.shadow)
    oc = parse_color(a.outline_color)
    pad = pad_for(a.outline, sh)
    for f in files:
        out = bake(Image.open(f), a.outline, oc, sh, pad, not a.four)
        base = os.path.splitext(os.path.basename(f))[0]
        dest = os.path.join(a.outdir, base + ".png")
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
        out.save(dest)
        if a.flash:
            flash(out, a.flash_amount).save(os.path.join(a.outdir, base + "_flash.png"))
    print(f"baked {len(files)} sprite(s), padding {pad}px -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
