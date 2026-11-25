#!/usr/bin/env python3
"""lut-tool: colour-grading look-up tables for game art and post-processing.

  identity --size 16 -o lut.png               neutral strip LUT (N slices of NxN laid out horizontally, width N*N, height N)
  make --brightness .1 --contrast 1.2 --gamma 1 --saturation .8 --hue 10 --tint ff9040 --tint-amount .2 -o warm.png
  apply image.png --lut warm.png -o graded.png   trilinear 3D lookup, alpha preserved
  to-cube lut.png -o warm.cube / from-cube warm.cube -o lut.png   Adobe/IRIDAS .cube text (LUT_3D_SIZE, red fastest)
Strip layout: slice index = blue, x inside the slice = red, y = green (the common Unity/Godot "LUT strip" convention).
"""
import os
import argparse, colorsys
import numpy as np
from PIL import Image
import sys


def identity(n=16):
    b, g, r = np.meshgrid(np.arange(n), np.arange(n), np.arange(n), indexing="ij")     # [b, g, r]
    lut = np.stack([r, g, b], -1) / (n - 1)                                              # [b, g, r, 3]
    return lut


def to_strip(lut):
    n = lut.shape[0]
    arr = (lut.transpose(1, 0, 2, 3).reshape(n, n * n, 3) * 255).round().astype(np.uint8)      # y=g, x=b*n+r
    return Image.fromarray(arr, "RGB")


def from_strip(img):
    a = np.array(img.convert("RGB")).astype(np.float64) / 255
    n = a.shape[0]
    if a.shape[1] != n * n: raise SystemExit(f"not a strip LUT: {a.shape[1]}x{a.shape[0]} (width must be height squared)")
    return a.reshape(n, n, n, 3).transpose(1, 0, 2, 3)                                           # [b, g, r, 3]


def adjust(rgb, brightness=0.0, contrast=1.0, gamma=1.0, saturation=1.0, hue=0.0, tint=None, tint_amount=0.0):
    x = np.clip(rgb, 0, 1)
    x = np.clip((x - 0.5) * contrast + 0.5 + brightness, 0, 1) ** (1.0 / max(gamma, 1e-6))
    if saturation != 1.0 or hue:
        flat = x.reshape(-1, 3); out = np.empty_like(flat)
        for i, (r, g, b) in enumerate(flat):
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            out[i] = colorsys.hsv_to_rgb((h + hue / 360.0) % 1.0, min(1.0, s * saturation), v)
        x = out.reshape(x.shape)
    if tint and tint_amount:
        tint = tint.lstrip("#"); t = np.array([int(tint[i:i + 2], 16) / 255 for i in (0, 2, 4)])
        lum = (x @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
        x = np.clip(x * (1 - tint_amount) + lum * t * 2 * tint_amount, 0, 1)
    return x


def make(n=16, **kw):
    return adjust(identity(n), **kw)


def apply(img, lut):
    n = lut.shape[0]
    a = np.array(img.convert("RGBA")).astype(np.float64)
    p = a[..., :3] / 255 * (n - 1)
    i0 = np.clip(np.floor(p).astype(int), 0, n - 2); f = p - i0
    r0, g0, b0 = i0[..., 0], i0[..., 1], i0[..., 2]; fr, fg, fb = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    out = 0
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = (fr if dr else 1 - fr) * (fg if dg else 1 - fg) * (fb if db else 1 - fb)
                out = out + w * lut[b0 + db, g0 + dg, r0 + dr]
    res = a.copy(); res[..., :3] = np.clip(out * 255, 0, 255).round()
    return Image.fromarray(res.astype(np.uint8), "RGBA")


def write_cube(path, lut, title="gst"):
    n = lut.shape[0]
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {n}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        for b in range(n):
            for g in range(n):
                for r in range(n):
                    f.write("%.6f %.6f %.6f\n" % tuple(lut[b, g, r]))


def read_cube(path):
    n, vals = None, []
    for line in open(path):
        p = line.split()
        if not p or p[0].startswith("#") or p[0] in ("TITLE", "DOMAIN_MIN", "DOMAIN_MAX"): continue
        if p[0] == "LUT_3D_SIZE": n = int(p[1]); continue
        if p[0] == "LUT_1D_SIZE": raise SystemExit("1D cube LUTs are not supported")
        vals.append([float(x) for x in p[:3]])
    if n is None or len(vals) != n ** 3: raise SystemExit("malformed .cube file")
    return np.array(vals).reshape(n, n, n, 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Colour grading LUT tool.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("identity"); s.add_argument("--size", type=int, default=16); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("make"); s.add_argument("--size", type=int, default=16); s.add_argument("-o", "--out", required=True)
    s.add_argument("--brightness", type=float, default=0); s.add_argument("--contrast", type=float, default=1); s.add_argument("--gamma", type=float, default=1)
    s.add_argument("--saturation", type=float, default=1); s.add_argument("--hue", type=float, default=0); s.add_argument("--tint"); s.add_argument("--tint-amount", type=float, default=0.25)
    s = sub.add_parser("apply"); s.add_argument("image"); s.add_argument("--lut", required=True); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("to-cube"); s.add_argument("lut"); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("from-cube"); s.add_argument("cube"); s.add_argument("-o", "--out", required=True)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    _src = getattr(a, 'image', None) or getattr(a, 'lut', None) or getattr(a, 'cube', None)
    if _src and getattr(a, 'out', None) and os.path.abspath(a.out) == os.path.abspath(_src) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if a.cmd == "identity": to_strip(identity(a.size)).save(a.out)
    elif a.cmd == "make": to_strip(make(a.size, brightness=a.brightness, contrast=a.contrast, gamma=a.gamma, saturation=a.saturation, hue=a.hue, tint=a.tint, tint_amount=a.tint_amount)).save(a.out)
    elif a.cmd == "apply": apply(Image.open(a.image), from_strip(Image.open(a.lut))).save(a.out)
    elif a.cmd == "to-cube": write_cube(a.out, from_strip(Image.open(a.lut)))
    else: to_strip(read_cube(a.cube)).save(a.out)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
