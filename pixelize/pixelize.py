#!/usr/bin/env python3
"""pixelize: turn concept art / generated images into game-ready pixel art.

Downscale (nearest or box), quantize to a palette (built-in, a .hex/.gpl file, or auto k-colours),
optional Floyd-Steinberg dithering, optional 1px outline, then upscale for preview.
"""
import argparse, os
from PIL import Image
import numpy as np
import os, sys

PALETTES = {
    # PICO-8 palette: colour values are facts, widely republished; used here as data only.
    "pico8": ["000000", "1D2B53", "7E2553", "008751", "AB5236", "5F574F", "C2C3C7", "FFF1E8",
              "FF004D", "FFA300", "FFEC27", "00E436", "29ADFF", "83769C", "FF77A8", "FFCCAA"],
    "gameboy": ["0F380F", "306230", "8BAC0F", "9BBC0F"],
    "mono": ["000000", "FFFFFF"],
}


def load_palette(spec):
    if spec in PALETTES:
        cols = PALETTES[spec]
    elif os.path.exists(spec):
        cols = []
        for line in open(spec, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line or line.startswith(("#", ";", "GIMP", "Name", "Columns")):
                continue
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):  # .gpl
                cols.append("%02X%02X%02X" % tuple(int(p) for p in parts[:3]))
            elif len(parts[0].lstrip("#")) == 6:  # .hex
                cols.append(parts[0].lstrip("#"))
    else:
        raise SystemExit(f"unknown palette {spec}")
    return [tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) for c in cols]


def quantize(img, palette=None, colors=16, dither=False):
    rgb = img.convert("RGB")
    d = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    if palette:
        pal_img = Image.new("P", (1, 1))
        flat = [v for c in palette for v in c]
        flat += flat[:3] * (256 - len(palette))
        pal_img.putpalette(flat)
        q = rgb.quantize(palette=pal_img, dither=d)
    else:
        q = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=d)
    return q.convert("RGB")


def outline(rgba, color=(0, 0, 0, 255)):
    a = np.array(rgba)
    alpha = a[..., 3] > 0
    grow = np.zeros_like(alpha)
    grow[1:, :] |= alpha[:-1, :]
    grow[:-1, :] |= alpha[1:, :]
    grow[:, 1:] |= alpha[:, :-1]
    grow[:, :-1] |= alpha[:, 1:]
    edge = grow & ~alpha
    a[edge] = color
    return Image.fromarray(a, "RGBA")


def pixelize(img, width=64, palette=None, colors=16, dither=False, do_outline=False, resample="box"):
    img = img.convert("RGBA")
    h = max(1, round(img.height * width / img.width))
    rs = Image.Resampling.BOX if resample == "box" else Image.Resampling.NEAREST
    small = img.resize((width, h), rs)
    alpha = small.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    q = quantize(small, palette, colors, dither).convert("RGBA")
    q.putalpha(alpha)
    if do_outline:
        q = outline(q)
    return q


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert an image to pixel art.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("-w", "--width", type=int, default=64, help="target width in pixels")
    ap.add_argument("-p", "--palette", help="pico8|gameboy|mono or a .hex/.gpl file")
    ap.add_argument("-c", "--colors", type=int, default=16, help="auto palette size when no --palette")
    ap.add_argument("--dither", action="store_true")
    ap.add_argument("--outline", action="store_true")
    ap.add_argument("--nearest", action="store_true", help="nearest downscale instead of box")
    ap.add_argument("--preview-scale", type=int, default=0, help="also save an upscaled preview (xN)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if getattr(a, 'out', None) and os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    pal = load_palette(a.palette) if a.palette else None
    out = pixelize(Image.open(a.input), a.width, pal, a.colors, a.dither, a.outline,
                   "nearest" if a.nearest else "box")
    out.save(a.out)
    if a.preview_scale > 1:
        base, ext = os.path.splitext(a.out)
        out.resize((out.width * a.preview_scale, out.height * a.preview_scale), Image.Resampling.NEAREST).save(f"{base}_x{a.preview_scale}{ext}")
    print(f"wrote {a.out} ({out.width}x{out.height})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
