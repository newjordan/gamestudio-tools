#!/usr/bin/env python3
"""sprite-pivot: compute pivot / origin points for sprite frames and export engine-ready offsets.

Modes: feet (bottom-centre of the opaque pixels: characters stand on the ground), center (bbox centre),
centroid (alpha-weighted centre of mass), top-left. --align-anim keeps one feet point for the whole
animation (median across frames) so a walk cycle does not jitter vertically or horizontally.
Output JSON per frame: pivot px, normalised pivot (Unity: origin bottom-left, y up), Godot Sprite2D offset
(pixels from the frame centre to move the texture so the pivot sits on the node origin).
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image
import os, sys


def frame_pivot(img, mode="feet"):
    a = np.array(img.convert("RGBA"))
    alpha = a[..., 3]
    ys, xs = np.where(alpha > 0)
    w, h = img.size
    if len(xs) == 0: return (w / 2, h / 2), (0, 0, 0, 0)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    if mode == "feet": p = ((x0 + x1) / 2, float(y1))
    elif mode == "center": p = ((x0 + x1) / 2, (y0 + y1) / 2)
    elif mode == "centroid":
        wt = alpha.astype(float); p = ((wt.sum(0) * (np.arange(w) + 0.5)).sum() / wt.sum(), (wt.sum(1) * (np.arange(h) + 0.5)).sum() / wt.sum())
    elif mode == "top-left": p = (float(x0), float(y0))
    else: raise SystemExit(f"unknown mode {mode}")
    return p, (int(x0), int(y0), int(x1), int(y1))


def export(name, size, pivot, bbox):
    w, h = size; px, py = pivot
    return {"frame": name, "size": [w, h], "bbox": list(bbox), "pivot_px": [round(px, 3), round(py, 3)],
            "unity_pivot": [round(px / w, 4), round(1 - py / h, 4)],
            "godot_offset": [round(w / 2 - px, 3), round(h / 2 - py, 3)]}


def process(files, mode="feet", align=False):
    imgs = [Image.open(f) for f in files]
    pv = [frame_pivot(i, mode) for i in imgs]
    pivots = [p for p, _ in pv]
    if align and pivots:
        med = (float(np.median([p[0] for p in pivots])), float(np.median([p[1] for p in pivots])))
        pivots = [med] * len(pivots)
    return [export(os.path.splitext(os.path.basename(f))[0], i.size, p, b) for f, i, p, (_, b) in zip(files, imgs, pivots, pv)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sprite pivot metadata.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs or a folder")
    ap.add_argument("--mode", default="feet", choices=["feet", "center", "centroid", "top-left"])
    ap.add_argument("--align-anim", action="store_true"); ap.add_argument("-o", "--out", required=True)
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
    _src_keys = ('inputs',)
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

    files = []
    for p in a.inputs: files += sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else sorted(glob.glob(p)) or [p]
    res = process(files, a.mode, a.align_anim)
    json.dump({"mode": a.mode, "aligned": a.align_anim, "frames": res}, open(a.out, "w"), indent=1)
    print(f"{len(res)} frame(s), mode {a.mode}{' (aligned)' if a.align_anim else ''} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
