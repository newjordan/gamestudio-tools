#!/usr/bin/env python3
"""parallax-preview: compose a scrolling parallax preview from layer PNGs, for title screens and side-scrollers.
Each layer has a horizontal (and optional vertical) speed relative to the camera: 0 is pinned, 1 scrolls with the
camera, 0.5 is half as fast. Layers are wrapped (they should already tile, or the image is treated as a repeating
strip). --width/--height set the viewport; --frames and --fps set the GIF length. --pixels is the camera travel in
pixels over the whole GIF (default: one viewport width). Output is a GIF (and optionally a first-frame PNG).
Foreground layers should be listed last (they draw on top).
"""
import argparse, os, sys

import numpy as np
from PIL import Image


def wrap_paste(dst, src, x, y):
    """Tile src onto dst so that (x, y) is the world-space origin of src, wrapping both axes."""
    sw, sh = src.size; dw, dh = dst.size
    x = int(x) % sw; y = int(y) % sh
    # cover the viewport by pasting starting at -x, -y
    yy = -y
    while yy < dh:
        xx = -x
        while xx < dw:
            dst.alpha_composite(src, (xx, yy)); xx += sw
        yy += sh


def render(layers, width, height, frames, travel_x, travel_y=0, bg=(20, 22, 28)):
    """layers: list of (Image, speed_x, speed_y). travel_* is camera movement across the whole animation."""
    out = []
    for i in range(frames):
        t = i / max(frames, 1)
        cam_x, cam_y = travel_x * t, travel_y * t
        canvas = Image.new("RGBA", (width, height), bg + (255,))
        for im, sx, sy in layers:
            wrap_paste(canvas, im.convert("RGBA"), cam_x * sx, cam_y * sy)
        out.append(canvas)
    return out


def parse_speeds(s, n):
    if not s:
        # default: back layers slower, last layer = 1
        if n == 1: return [(1.0, 0.0)]
        return [((i / (n - 1)), 0.0) for i in range(n)]
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != n: raise SystemExit(f"--speeds has {len(parts)} value(s) but there are {n} layer(s)")
    out = []
    for p in parts:
        if ":" in p: a, b = p.split(":", 1); out.append((float(a), float(b)))
        else: out.append((float(p), 0.0))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scrolling parallax GIF from layer PNGs.")
    ap.add_argument("layers", nargs="+", help="layer PNGs, back to front")
    ap.add_argument("-o", "--out", required=True, help="output GIF")
    ap.add_argument("--speeds", help="comma list of horizontal speeds, or x:y pairs, back to front (default: 0 .. 1)")
    ap.add_argument("--width", type=int); ap.add_argument("--height", type=int)
    ap.add_argument("--frames", type=int, default=24); ap.add_argument("--fps", type=float, default=12)
    ap.add_argument("--pixels", type=float, help="horizontal camera travel in px (default: viewport width)")
    ap.add_argument("--pixels-y", type=float, default=0); ap.add_argument("--bg", default="#14161c")
    ap.add_argument("--png", help="also write the first frame as a PNG")
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
    _src_keys = ('layers',)
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

    ims = [Image.open(p).convert("RGBA") for p in a.layers]
    w = a.width or ims[-1].width; h = a.height or ims[-1].height
    speeds = parse_speeds(a.speeds, len(ims))
    bg = tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    travel = a.pixels if a.pixels is not None else w
    frames = render(list(zip(ims, [s[0] for s in speeds], [s[1] for s in speeds])), w, h, a.frames, travel, a.pixels_y, bg)
    dur = max(1, int(round(1000 / a.fps)))
    frames[0].convert("RGB").save(a.out, save_all=True, append_images=[f.convert("RGB") for f in frames[1:]], duration=dur, loop=0)
    if a.png: frames[0].save(a.png)
    print(f"{len(ims)} layer(s), {a.frames} frame(s) at {w}x{h}, travel {travel:g} px -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
