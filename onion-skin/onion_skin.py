#!/usr/bin/env python3
"""onion-skin: animator review sheet. For each frame of an animation, draw the previous frame(s) ghosted in one tint and the next
frame(s) in another, with the frame itself on top, so arcs, spacing and pops are visible on one image. Input: a folder of PNGs
(natural order), an animated GIF/APNG/WebP, or a sprite sheet with --grid WxH. Output: a strip/grid PNG (--cols), optionally an
animated GIF of the onion frames. --loop treats the animation as a cycle (frame 0 follows the last). The report lists how much of the
drawing changes (colour differences up to --tolerance are ignored) between consecutive frames and flags DUPLICATE (nothing changed) and POP (more than --pop of the pixels changed).
"""
import argparse, os, glob, re, sys

import numpy as np
from PIL import Image

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "gif-to-frames")); sys.path.insert(0, os.path.join(here, "..", "sprite-slice"))
import gif_to_frames, sprite_slice  # noqa: E402


def natural(s): return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def load_frames(path, grid=None):
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.png")), key=natural)
        if not files: raise SystemExit("no PNG frames in that folder")
        ims = [Image.open(f).convert("RGBA") for f in files]
    elif grid:
        sheet = Image.open(path).convert("RGBA"); fw, fh = grid
        ims = [sheet.crop(b) for b in sprite_slice.grid_slice(sheet, fw, fh)]
    else:
        ims = [f for f, _ in gif_to_frames.split(path)[0]]
    W = max(i.width for i in ims); H = max(i.height for i in ims); out = []
    for i in ims:
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); c.paste(i, ((W - i.width) // 2, H - i.height)); out.append(c)         # bottom-centre align different sizes
    return out


def tint(im, color, opacity, mix=0.65):
    a = np.array(im).astype(np.float32); rgb = a[..., :3] * (1 - mix) + np.array(color, np.float32) * mix
    a[..., :3] = rgb; a[..., 3] = a[..., 3] * opacity; return Image.fromarray(a.astype(np.uint8), "RGBA")


def onion(frames, i, prev=1, nxt=1, loop=False, bg=None, prev_color=(255, 70, 70), next_color=(70, 130, 255), opacity=0.5, fade=0.6):
    n = len(frames); canvas = Image.new("RGBA", frames[0].size, bg + (255,) if bg else (0, 0, 0, 0))
    def idx(k): j = i + k; return j % n if loop else (j if 0 <= j < n else None)
    for k in range(max(prev, nxt), 0, -1):                                           # farthest ghosts first
        for sign, cnt, col in ((-1, prev, prev_color), (1, nxt, next_color)):
            if k <= cnt:
                j = idx(sign * k)
                if j is not None and j != i: canvas = Image.alpha_composite(canvas, tint(frames[j], col, opacity * fade ** (k - 1)))
    return Image.alpha_composite(canvas, frames[i])


def changes(frames, loop=False, pop=0.6, tolerance=12):
    n = len(frames); rows = []
    for i in range(n - (0 if loop else 1)):
        a, b = np.array(frames[i]), np.array(frames[(i + 1) % n]); op = (a[..., 3] > 0) | (b[..., 3] > 0)
        diff = (np.abs(a.astype(int) - b.astype(int)).max(-1) > tolerance) & op; tot = int(op.sum()); ratio = float(diff.sum() / tot) if tot else 0.0
        rows.append({"from": i, "to": (i + 1) % n, "changed": round(ratio, 3), "flag": "DUPLICATE" if diff.sum() == 0 else "POP" if ratio > pop else ""})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Onion-skin review sheet for an animation.")
    ap.add_argument("input", help="folder of PNGs, animated GIF/APNG/WebP, or sheet PNG with --grid"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--grid", help="frame size WxH when INPUT is a sprite sheet"); ap.add_argument("--prev", type=int, default=1); ap.add_argument("--next", type=int, default=1)
    ap.add_argument("--loop", action="store_true"); ap.add_argument("--cols", type=int, default=0, help="frames per row in the sheet (default: all in one row)")
    ap.add_argument("--bg", default="#303038"); ap.add_argument("--scale", type=int, default=1); ap.add_argument("--gif", help="also write an animated GIF"); ap.add_argument("--fps", type=int, default=6)
    ap.add_argument("--pop", type=float, default=0.6); ap.add_argument("--tolerance", type=int, default=12, help="ignore per-channel differences up to this (dither, compression noise)"); ap.add_argument("--opacity", type=float, default=0.5)
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

    grid = tuple(int(v) for v in a.grid.lower().split("x")) if a.grid else None
    frames = load_frames(a.input, grid); bg = tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    ons = [onion(frames, i, a.prev, a.next, a.loop, bg, opacity=a.opacity) for i in range(len(frames))]
    if a.scale != 1: ons = [o.resize((o.width * a.scale, o.height * a.scale), Image.NEAREST) for o in ons]
    cols = a.cols or len(ons); rows = -(-len(ons) // cols); w, h = ons[0].size
    sheet = Image.new("RGBA", (cols * w, rows * h), bg + (255,))
    for i, o in enumerate(ons): sheet.paste(o, ((i % cols) * w, (i // cols) * h))
    sheet.convert("RGB").save(a.out)
    if a.gif: ons[0].convert("RGB").save(a.gif, save_all=True, append_images=[o.convert("RGB") for o in ons[1:]], duration=int(1000 / a.fps), loop=0)
    rep = changes(frames, a.loop, a.pop, a.tolerance)
    for r in rep: print(f"frame {r['from']:>2} -> {r['to']:<2} changed {r['changed'] * 100:5.1f}% {r['flag']}")
    flags = [r for r in rep if r["flag"]]; print(f"{len(frames)} frame(s), {len(flags)} flagged -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
