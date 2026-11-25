#!/usr/bin/env python3
"""frames-to-sheet: turn an animated GIF/APNG/WebP (or a folder of frames) into a game-ready sprite sheet
plus JSON (frame rects and per-frame durations). Optional uniform crop (shared bbox so frames stay aligned),
scale (nearest), transparent-colour key, and --max-frames subsampling.
Use after video/animation generators (e.g. H3 clips -> GIF) or when importing an artist's GIF.
"""
import argparse, glob, json, math, os
import numpy as np
from PIL import Image, ImageSequence
import os, sys


def read_frames(path):
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.png")))
        return [Image.open(f).convert("RGBA") for f in files], [100] * len(files)
    im = Image.open(path)
    fr, du = [], []
    for f in ImageSequence.Iterator(im):
        fr.append(f.convert("RGBA")); du.append(int(f.info.get("duration", 100)))
    return fr, du


def key_out(img, rgb, tol=8):
    a = np.array(img)
    m = np.abs(a[..., :3].astype(int) - np.array(rgb)).max(-1) <= tol
    a[m, 3] = 0
    return Image.fromarray(a, "RGBA")


def union_bbox(frames):
    boxes = [f.getchannel("A").getbbox() for f in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        return (0, 0) + frames[0].size
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def build(frames, durations, columns=0, crop=True, scale=1, padding=0):
    if crop:
        bb = union_bbox(frames)
        frames = [f.crop(bb) for f in frames]
    if scale > 1:
        frames = [f.resize((f.width * scale, f.height * scale), Image.Resampling.NEAREST) for f in frames]
    fw, fh = frames[0].size
    n = len(frames)
    cols = columns or math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    sheet = Image.new("RGBA", (cols * (fw + padding) + padding, rows * (fh + padding) + padding), (0, 0, 0, 0))
    meta = []
    for i, f in enumerate(frames):
        x, y = padding + (i % cols) * (fw + padding), padding + (i // cols) * (fh + padding)
        sheet.paste(f, (x, y))
        meta.append({"index": i, "x": x, "y": y, "w": fw, "h": fh, "duration_ms": durations[i]})
    return sheet, {"frame_width": fw, "frame_height": fh, "columns": cols, "rows": rows, "count": n,
                   "total_ms": sum(durations), "frames": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Animated image / frame folder -> sprite sheet + JSON.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True, help="output basename (.png + .json)")
    ap.add_argument("--columns", type=int, default=0)
    ap.add_argument("--no-crop", action="store_true")
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--padding", type=int, default=0)
    ap.add_argument("--key", help="hex colour to make transparent, e.g. 00ff00")
    ap.add_argument("--max-frames", type=int, help="evenly subsample down to this many frames")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    for _cand in (a.out, a.out + '.png', a.out + '.json'):
        if os.path.abspath(_cand) == os.path.abspath(a.input) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    fr, du = read_frames(a.input)
    if a.key:
        fr = [key_out(f, tuple(int(a.key[i:i + 2], 16) for i in (0, 2, 4))) for f in fr]
    if a.max_frames and len(fr) > a.max_frames:
        step = len(fr) / a.max_frames
        pick = [int(i * step) for i in range(a.max_frames)]
        du = [int(sum(du[pick[k]:(pick[k + 1] if k + 1 < len(pick) else len(du))])) for k in range(len(pick))]
        fr = [fr[i] for i in pick]
    sheet, meta = build(fr, du, a.columns, not a.no_crop, a.scale, a.padding)
    sheet.save(a.out + ".png")
    json.dump(meta, open(a.out + ".json", "w"), indent=1)
    print(f"{meta['count']} frames of {meta['frame_width']}x{meta['frame_height']} -> {a.out}.png ({sheet.width}x{sheet.height}), {meta['total_ms']} ms")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
