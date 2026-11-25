#!/usr/bin/env python3
"""alpha-bleed: stop dark or light fringes around sprites that get filtered or mip-mapped. Pixels with alpha 0 usually carry
black (or whatever the paint program left) in their RGB; bilinear filtering blends that into the sprite's edge. This tool copies the
nearest opaque colours outward into the fully transparent pixels (RGB only: alpha is never touched, so the picture looks identical).
Works by repeated dilation: each pass fills transparent pixels that touch filled ones with the average of those neighbours, up to
--distance passes (default 16; 0 = until nothing changes). --threshold treats alpha <= N as "transparent" for the fill source
rule (default 0: only fully transparent pixels are overwritten, only pixels with alpha > 0 are sources). Files or folders in, same
names out.
"""
import argparse, os, glob, sys

import numpy as np
from PIL import Image


def bleed(img, distance=16, threshold=0):
    a = np.array(img.convert("RGBA")); rgb = a[..., :3].astype(np.float32); al = a[..., 3]
    filled = al > threshold; target = al <= threshold          # pixels whose RGB may be rewritten
    h, w = al.shape; passes = 0; limit = distance if distance > 0 else h + w
    while passes < limit:
        todo = target & ~filled
        if not todo.any(): break
        acc = np.zeros_like(rgb); cnt = np.zeros((h, w), np.float32)
        f = filled.astype(np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0: continue
                ys, ye = max(dy, 0), h + min(dy, 0); xs, xe = max(dx, 0), w + min(dx, 0)          # destination window
                sy, se = max(-dy, 0), h + min(-dy, 0); sx, sxe = max(-dx, 0), w + min(-dx, 0)      # matching source window
                acc[ys:ye, xs:xe] += rgb[sy:se, sx:sxe] * f[sy:se, sx:sxe, None]; cnt[ys:ye, xs:xe] += f[sy:se, sx:sxe]
        new = todo & (cnt > 0)
        if not new.any(): break
        rgb[new] = acc[new] / cnt[new, None]; filled = filled | new; passes += 1
    a[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    changed = int((target & filled & (al <= threshold)).sum())
    return Image.fromarray(a, "RGBA"), {"passes": passes, "pixels_filled": changed}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bleed edge colours into transparent pixels to avoid filtering halos.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs or folders"); ap.add_argument("-o", "--out", required=True, help="output folder (or file for a single input)")
    ap.add_argument("--distance", type=int, default=16, help="max passes (pixels of bleed), 0 = unlimited"); ap.add_argument("--threshold", type=int, default=0)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = []
    for p in a.inputs:
        files += sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else (sorted(glob.glob(p)) or [p])
    if not files: sys.exit("no input images")
    missing = [f for f in files if not os.path.exists(f)]
    if missing: sys.exit(f"not found: {missing[0]}")
    single = len(files) == 1 and not os.path.isdir(a.out) and os.path.splitext(a.out)[1].lower() == ".png"
    if not single: os.makedirs(a.out, exist_ok=True)
    for f in files:
        out, st = bleed(Image.open(f), a.distance, a.threshold)
        dst = a.out if single else os.path.join(a.out, os.path.basename(f))
        if os.path.abspath(dst) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
        out.save(dst)
        print(f"{f}: {st['pixels_filled']} transparent pixels coloured in {st['passes']} pass(es) -> {dst}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
