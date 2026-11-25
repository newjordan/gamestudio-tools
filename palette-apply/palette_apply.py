#!/usr/bin/env python3
"""palette-apply: force sprites onto a palette (nearest colour, optional
Floyd–Steinberg dither). The palette comes from a `.hex` / `.gpl` file, a
JSON list, or is extracted from a reference image (via palette-swap's reader,
or the unique opaque colours of a PNG). Alpha is kept (transparent pixels stay
transparent). Folders or files in; writes `-o`. The input is never overwritten
unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "palette-swap"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pixelize"))
import safe_out, sprite_rotate, palette_swap, pixelize  # noqa: E402


def load_palette(spec):
    if os.path.isfile(spec) and spec.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")):
        im = Image.open(spec).convert("RGBA")
        a = np.array(im)
        rgb = a[..., :3][a[..., 3] >= 128]
        cols = [tuple(int(x) for x in row) for row in np.unique(rgb, axis=0)]
        if not cols:
            raise SystemExit(f"{spec}: no opaque pixels to build a palette from")
        return cols
    if os.path.isfile(spec) and spec.lower().endswith(".json"):
        data = json.load(open(spec, encoding="utf-8"))
        if isinstance(data, dict) and "palette" in data:
            data = data["palette"]
        cols = []
        for item in data:
            if isinstance(item, str):
                cols.append(palette_swap.hexrgb(item))
            else:
                cols.append(tuple(int(x) for x in item[:3]))
        return cols
    # .hex / .gpl or a named pixelize palette
    try:
        return pixelize.load_palette(spec)
    except SystemExit:
        if os.path.isfile(spec):
            cols = palette_swap.read_palette(spec)
            if cols:
                return cols
        raise


def apply(im, palette, dither):
    im = im.convert("RGBA")
    alpha = im.getchannel("A")
    q = pixelize.quantize(im, palette=palette, dither=dither).convert("RGBA")
    # restore original alpha (quantize is RGB-only)
    q.putalpha(alpha)
    # fully transparent pixels: leave RGB as the quantized value; alpha 0
    return q


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    return os.path.join(outdir, f"{stem}{suffix}{ext}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Force sprites onto a palette (nearest colour or Floyd–Steinberg).")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--palette", required=True, help=".hex / .gpl / .json / image, or a pixelize built-in name")
    ap.add_argument("--dither", action="store_true", help="Floyd–Steinberg dither (default: nearest colour)")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    palette = load_palette(a.palette)
    if not palette:
        sys.exit("palette is empty")
    paths = sprite_rotate.collect(a.inputs)
    if not paths:
        sys.exit("no images found")
    out_is_dir = (os.path.isdir(a.out) or len(paths) > 1
                  or not a.out.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")))
    if out_is_dir:
        os.makedirs(a.out, exist_ok=True)
        out_file, outdir = None, a.out
    else:
        out_file, outdir = a.out, None
    recs = []
    for p in paths:
        dest = dest_of(p, outdir or os.path.dirname(os.path.abspath(out_file)), a.suffix, out_file)
        safe_out.check(p, dest, a.in_place)
        if a.json:
            safe_out.check(p, a.json, a.in_place)
        im = Image.open(p)
        out = apply(im, palette, a.dither)
        os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
        out.save(dest)
        recs.append({"file": p, "out": dest, "palette": len(palette)})
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "palette_size": len(palette), "dither": a.dither},
                  open(a.json, "w"), indent=2)
    print(f"{len(recs)} image(s) mapped to {len(palette)} colour(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
