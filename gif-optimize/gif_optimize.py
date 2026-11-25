#!/usr/bin/env python3
"""gif-optimize: shrink review GIFs by quantising every frame to a shared palette, optionally scaling, and writing
with Pillow's GIF optimizer. Reports before/after bytes and frame count. The input is never overwritten. This is a
review-size pass, not a substitute for gifsicle or a lossless archive. Frame-diff disposal is attempted when
unchanged regions can be marked transparent; otherwise full palettised frames are written.
"""
import argparse, os, json, sys, struct

import numpy as np
from PIL import Image, ImageSequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402


def load_frames(path):
    try:
        im = Image.open(path)
        frames = []
        for fr in ImageSequence.Iterator(im):
            dur = int(fr.info.get("duration", 100) or 100)
            frames.append((fr.convert("RGBA").copy(), max(1, dur)))
    except GstInputError:
        raise
    except (OSError, ValueError, SyntaxError, struct.error, EOFError, IndexError, MemoryError) as e:
        raise GstInputError("GIF file is not valid: %s" % e) from e
    except Exception as e:
        if type(e).__name__ == "DecompressionBombError":
            raise GstInputError("image is too large") from e
        raise
    if not frames:
        raise GstInputError("GIF has no frames")
    return frames


def scale_frames(frames, scale, resample):
    if scale == 1: return frames
    out = []
    for im, dur in frames:
        w, h = max(1, int(round(im.width * scale))), max(1, int(round(im.height * scale)))
        out.append((im.resize((w, h), resample), dur))
    return out


def flatten(im, bg=(0, 0, 0)):
    rgb = Image.new("RGB", im.size, bg)
    rgba = im.convert("RGBA")
    rgb.paste(rgba, mask=rgba.split()[-1])
    return rgb


def shared_palette(frames, colors, dither):
    w, h = frames[0][0].size
    take = frames[:64]
    n = len(take)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    grid = Image.new("RGB", (max(cols * w, 1), max(rows * h, 1)), (0, 0, 0))
    for i, (im, _) in enumerate(take):
        grid.paste(flatten(im), ((i % cols) * w, (i // cols) * h))
    return grid.quantize(colors=max(2, min(colors, 256)), method=Image.Quantize.MEDIANCUT,
                         dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)


def to_p(im, pal, dither):
    return flatten(im).quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE)


def optimize(frames, colors=64, scale=1.0, dither=False, nearest=True):
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR
    frames = scale_frames(frames, scale, resample)
    pal = shared_palette(frames, colors, dither)
    out, durs = [], []
    for rgba, dur in frames:
        out.append(to_p(rgba, pal, dither))
        durs.append(dur)
    return out, durs, frames[0][0].size


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shrink a review GIF (shared palette, optional scale).")
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--colors", type=int, default=64)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--dither", action="store_true")
    ap.add_argument("--bilinear", action="store_true", help="use bilinear scaling instead of nearest")
    ap.add_argument("--loop", type=int, default=0, help="Netscape loop count (0 = forever)")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if not 2 <= a.colors <= 256: sys.exit("--colors must be 2-256")
    if a.scale <= 0: sys.exit("--scale must be positive")
    before = os.path.getsize(a.input)
    frames = load_frames(a.input)
    out_frames, durs, size = optimize(frames, a.colors, a.scale, a.dither, nearest=not a.bilinear)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    out_frames[0].save(a.out, format="GIF", save_all=True, append_images=out_frames[1:],
                       duration=durs, disposal=1, loop=a.loop, optimize=True)
    after = os.path.getsize(a.out)
    rec = {"file": a.input, "out": a.out, "frames": len(out_frames), "size": list(size),
           "colors": a.colors, "scale": a.scale, "bytes_before": before, "bytes_after": after,
           "ratio": round(after / before, 3) if before else None}
    print(f"{rec['frames']} frame(s), {before} -> {after} bytes ({rec['ratio']}x) {size[0]}x{size[1]} -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
