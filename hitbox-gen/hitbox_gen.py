#!/usr/bin/env python3
"""hitbox-gen: derive collision shapes from sprite alpha, for 2D engine import. For each image (or each cell of a
--grid sheet, or each named frame of an atlas JSON) it writes:
  aabb     tight axis-aligned box around opaque pixels, expanded by --pad
  circle   centre at the box centre (or the opaque-pixel centroid with --centroid) and radius to the farthest
           opaque pixel, plus --pad
  capsule  a stadium: vertical if the box is taller than it is wide, otherwise horizontal; radius is half the
           shorter side plus --pad, and the shaft is the leftover length of the longer side
Coordinates are in pixels, origin at the top-left of the input (y down). --normalized writes 0..1 fractions of
the image size as well. Fully transparent images get a zero-size aabb and a null circle/capsule. JSON output.
"""
import argparse, os, glob, json, math, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-slice"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spritesheet-gif"))
import sprite_slice, spritesheet_gif  # noqa: E402


def shapes(im, pad=0, threshold=0, centroid=False):
    a = np.array(im.convert("RGBA")); h, w = a.shape[:2]; solid = a[..., 3] > threshold
    ys, xs = np.where(solid)
    if len(xs) == 0:
        return {"w": w, "h": h, "empty": True, "aabb": {"x": 0, "y": 0, "w": 0, "h": 0}, "circle": None, "capsule": None}
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    aabb = {"x": x0 - pad, "y": y0 - pad, "w": (x1 - x0) + 2 * pad, "h": (y1 - y0) + 2 * pad}
    if centroid:
        cx, cy = float(xs.mean()) + 0.5, float(ys.mean()) + 0.5
    else:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = float(np.sqrt((xs + 0.5 - cx) ** 2 + (ys + 0.5 - cy) ** 2).max()) + pad
    circle = {"cx": cx, "cy": cy, "r": r}
    bw, bh = x1 - x0, y1 - y0
    if bh >= bw:
        rad = bw / 2 + pad; shaft = max(0.0, bh - bw); capsule = {"cx": cx, "cy": cy, "r": rad, "length": shaft, "axis": "y"}
    else:
        rad = bh / 2 + pad; shaft = max(0.0, bw - bh); capsule = {"cx": cx, "cy": cy, "r": rad, "length": shaft, "axis": "x"}
    return {"w": w, "h": h, "empty": False, "aabb": aabb, "circle": circle, "capsule": capsule}


def normalize(s):
    w, h = s["w"], s["h"]
    def nbox(b):
        if not b: return b
        out = dict(b)
        if "x" in b: out["x"] = b["x"] / w if w else 0; out["y"] = b["y"] / h if h else 0; out["w"] = b["w"] / w if w else 0; out["h"] = b["h"] / h if h else 0
        if "cx" in b: out["cx"] = b["cx"] / w if w else 0; out["cy"] = b["cy"] / h if h else 0; out["r"] = b["r"] / max(w, h) if max(w, h) else 0
        if "length" in b: out["length"] = b["length"] / (h if b.get("axis") == "y" else w) if (h if b.get("axis") == "y" else w) else 0
        return out
    return {**s, "aabb": nbox(s["aabb"]), "circle": nbox(s["circle"]), "capsule": nbox(s["capsule"]), "normalized": True}


def load(paths, grid=None, atlas=None):
    items = []
    if atlas:
        meta = json.load(open(atlas)); img = None
        image = os.path.join(os.path.dirname(os.path.abspath(atlas)), (meta.get("meta") or {}).get("image") or "")
        if not os.path.isfile(image): raise SystemExit(f"atlas image not found: {image}")
        sheet = Image.open(image).convert("RGBA"); fr = spritesheet_gif.load_atlas_frames(meta, atlas)
        for name in fr: items.append((name, spritesheet_gif.reconstruct(sheet, fr, name, None)))
        return items
    if grid and len(paths) == 1 and not os.path.isdir(paths[0]):
        sheet = Image.open(paths[0]).convert("RGBA")
        for i, b in enumerate(sprite_slice.grid_slice(sheet, *grid)): items.append((f"frame_{i:04d}", sheet.crop(b)))
        return items
    for p in paths:
        batch = sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else (sorted(glob.glob(p)) or [p])
        for f in batch: items.append((os.path.splitext(os.path.basename(f))[0], Image.open(f)))
    if not items: raise SystemExit("no input images")
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description="Collision shapes (AABB, circle, capsule) from sprite alpha.")
    ap.add_argument("inputs", nargs="*"); ap.add_argument("-o", "--out", required=True, help="output JSON")
    ap.add_argument("--pad", type=float, default=0); ap.add_argument("--threshold", type=int, default=0)
    ap.add_argument("--centroid", action="store_true"); ap.add_argument("--normalized", action="store_true")
    ap.add_argument("--grid"); ap.add_argument("--atlas", help="atlas JSON (frames are reconstructed with trim offsets)")
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

    if not a.inputs and not a.atlas: sys.exit("give image inputs or --atlas")
    grid = tuple(int(v) for v in a.grid.lower().split("x")) if a.grid else None
    frames = {}
    for name, im in load(a.inputs, grid, a.atlas):
        s = shapes(im, a.pad, a.threshold, a.centroid)
        frames[name] = normalize(s) if a.normalized else s
    json.dump({"frames": frames, "pad": a.pad, "threshold": a.threshold}, open(a.out, "w"), indent=1)
    print(f"{len(frames)} frame(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
