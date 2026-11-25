#!/usr/bin/env python3
"""sprite-slice: cut a sprite sheet into frames (grid or auto-detect), trim, and preview as GIF."""
import argparse, os, json
from PIL import Image
import numpy as np
import os, sys


def grid_slice(img, fw, fh, margin=0, spacing=0):
    frames = []
    y = margin
    while y + fh <= img.height - margin + 0:
        x = margin
        while x + fw <= img.width - margin + 0:
            frames.append(((x, y, x + fw, y + fh)))
            x += fw + spacing
        y += fh + spacing
    return frames


def auto_slice(img, min_area=4):
    """Find connected opaque islands (4-neighbour) and return their bboxes, row-major order."""
    a = np.array(img.getchannel("A")) > 0
    h, w = a.shape
    seen = np.zeros_like(a)
    boxes = []
    for y in range(h):
        for x in range(w):
            if a[y, x] and not seen[y, x]:
                stack = [(y, x)]
                seen[y, x] = True
                x0 = x1 = x
                y0 = y1 = y
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h and 0 <= nx < w and a[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if n >= min_area:
                    boxes.append((x0, y0, x1 + 1, y1 + 1))
    # row-major: group by approximate row
    boxes.sort(key=lambda b: (b[1] // 8, b[0]))
    return boxes


def is_empty(img):
    return img.getchannel("A").getbbox() is None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Slice a sprite sheet into frames.")
    ap.add_argument("sheet")
    ap.add_argument("-o", "--out", default="frames")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--grid", help="frame size WxH, e.g. 32x32")
    g.add_argument("--auto", action="store_true", help="detect sprite islands by alpha")
    ap.add_argument("--margin", type=int, default=0)
    ap.add_argument("--spacing", type=int, default=0)
    ap.add_argument("--keep-empty", action="store_true")
    ap.add_argument("--gif", help="also write an animated GIF preview here")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--prefix", default="frame")
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
    _src_keys = ('sheet',)
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

    img = Image.open(a.sheet).convert("RGBA")
    if a.grid:
        fw, fh = (int(v) for v in a.grid.lower().split("x"))
        boxes = grid_slice(img, fw, fh, a.margin, a.spacing)
    else:
        boxes = auto_slice(img)
    os.makedirs(a.out, exist_ok=True)
    frames, index = [], []
    for b in boxes:
        fr = img.crop(b)
        if not a.keep_empty and is_empty(fr):
            continue
        name = f"{a.prefix}_{len(frames):03d}.png"
        fr.save(os.path.join(a.out, name))
        frames.append(fr)
        index.append({"file": name, "x": b[0], "y": b[1], "w": b[2] - b[0], "h": b[3] - b[1]})
    with open(os.path.join(a.out, "frames.json"), "w") as f:
        json.dump(index, f, indent=2)
    if a.gif and frames:
        W = max(f.width for f in frames)
        H = max(f.height for f in frames)
        canv = []
        for fr in frames:
            c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            c.paste(fr, ((W - fr.width) // 2, H - fr.height))
            canv.append(c)
        canv[0].save(a.gif, save_all=True, append_images=canv[1:], duration=int(1000 / a.fps), loop=0, disposal=2)
    print(f"wrote {len(frames)} frames to {a.out}" + (f", preview {a.gif}" if a.gif else ""))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
