#!/usr/bin/env python3
"""sprite-trim: crop transparent margins from sprites and write a bbox / trim JSON (atlas-pack
`spriteSourceSize` / `sourceSize` shape). Files, globs or a folder in; same basenames out.
Writes new files; inputs are never overwritten unless `--in-place`.
"""
import argparse, os, glob, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402
from PIL import Image


def collect(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.png"))))
        else:
            files.extend(sorted(glob.glob(p)) or [p])
    return [f for f in files if f.lower().endswith(".png")]


def trim_box(im):
    im = im.convert("RGBA")
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return im, (0, 0, im.width, im.height), True
    return im.crop(bbox), bbox, False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trim transparent margins from sprites and write a bbox JSON.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs, or a folder")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--json", help="write a trim report (spriteSourceSize / sourceSize per file)")
    ap.add_argument("--min-alpha", type=int, default=1, help="alpha below this counts as transparent (default 1)")
    ap.add_argument("--padding", type=int, default=0, help="pixels to keep around the opaque bbox")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    files = collect(a.inputs)
    if not files:
        sys.exit("no PNGs found")
    os.makedirs(a.outdir, exist_ok=True)
    if a.json:
        safe_out.check_any(files, a.json, a.in_place)
    frames = {}
    for f in files:
        dest = os.path.join(a.outdir, os.path.basename(f))
        safe_out.check(f, dest, a.in_place)
        im = Image.open(f).convert("RGBA")
        if a.min_alpha > 1:
            px = np_alpha = None
            arr = __import__("numpy").array(im)
            mask = arr[:, :, 3] >= a.min_alpha
            if not mask.any():
                bbox = None
            else:
                ys, xs = mask.nonzero()
                bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        else:
            bbox = im.getchannel("A").getbbox()
        empty = bbox is None
        if empty:
            bbox = (0, 0, im.width, im.height)
            cropped = im
        else:
            x0, y0, x1, y1 = bbox
            x0 = max(0, x0 - a.padding)
            y0 = max(0, y0 - a.padding)
            x1 = min(im.width, x1 + a.padding)
            y1 = min(im.height, y1 + a.padding)
            bbox = (x0, y0, x1, y1)
            cropped = im.crop(bbox)
        cropped.save(dest)
        name = os.path.splitext(os.path.basename(f))[0]
        frames[name] = {
            "frame": {"x": 0, "y": 0, "w": cropped.width, "h": cropped.height},
            "trimmed": not empty and bbox != (0, 0, im.width, im.height),
            "empty": empty,
            "spriteSourceSize": {"x": bbox[0], "y": bbox[1], "w": cropped.width, "h": cropped.height},
            "sourceSize": {"w": im.width, "h": im.height},
            "file": os.path.basename(dest),
        }
    rec = {"frames": frames, "count": len(frames)}
    print(f"trimmed {len(frames)} sprite(s) -> {a.outdir}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
