#!/usr/bin/env python3
"""gif-to-frames: split an animated GIF (also APNG / animated WebP, whatever Pillow can open) into numbered PNG frames
with per-frame durations, for importing reference animations or recovering lost source frames. Frames are fully
composited (disposal handled by Pillow). Writes frames.json (durations in ms, loop count, size) and optionally a
horizontal strip sheet. --merge-same collapses runs of identical consecutive frames and adds their durations.
"""
import argparse, os, json, sys, struct

import numpy as np
from PIL import Image, ImageSequence

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402


def merge(frames):
    """Collapse runs of identical consecutive frames, adding up their durations."""
    out = []
    for f, d in frames:
        if out and np.array_equal(np.array(out[-1][0]), np.array(f)): out[-1] = (out[-1][0], out[-1][1] + d)
        else: out.append((f, d))
    return out


def split(path, merge_same=False):
    try:
        im = Image.open(path)
        frames = []
        for fr in ImageSequence.Iterator(im):
            rgba = fr.convert("RGBA")
            d = int(fr.info.get("duration", im.info.get("duration", 100)) or 0)
            frames.append((rgba.copy(), d))
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
    if merge_same:
        frames = merge(frames)
    return frames, {"loop": im.info.get("loop", 1 if getattr(im, "n_frames", 1) > 1 else 0), "size": list(im.size), "format": im.format}


def strip(frames):
    w, h = frames[0][0].size; s = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, (f, _) in enumerate(frames): s.paste(f, (i * w, 0))
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split an animated GIF/APNG/WebP into PNG frames + timings.")
    ap.add_argument("input"); ap.add_argument("-o", "--outdir", default="frames"); ap.add_argument("--prefix", default="frame")
    ap.add_argument("--merge-same", action="store_true", help="collapse identical consecutive frames, summing their durations")
    ap.add_argument("--strip", action="store_true", help="also write <prefix>_strip.png (all frames side by side)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('input',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    frames, info = split(a.input, a.merge_same)
    os.makedirs(a.outdir, exist_ok=True); names = []
    for i, (f, d) in enumerate(frames):
        n = f"{a.prefix}_{i:04d}.png"; f.save(os.path.join(a.outdir, n)); names.append({"file": n, "duration_ms": d})
    meta = dict(info, frames=names, total_ms=sum(d for _, d in frames))
    json.dump(meta, open(os.path.join(a.outdir, "frames.json"), "w"), indent=2)
    if a.strip: strip(frames).save(os.path.join(a.outdir, f"{a.prefix}_strip.png"))
    ds = {d for _, d in frames}
    print(f"{len(frames)} frames, {meta['total_ms']} ms total ({'constant ' + str(ds.pop()) + ' ms' if len(ds) == 1 else 'variable timing'}) -> {a.outdir}")
    if any(d == 0 for _, d in frames): print("WARN some frames have 0 ms duration (browsers usually treat that as 100 ms)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
