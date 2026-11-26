#!/usr/bin/env python3
"""atlas-validate: check an atlas JSON (hash or array layout, as written by atlas-pack) against its PNG.
Errors: frame outside the image, overlapping frames, duplicate names, missing image.
Identical rectangles that resolve to the same frame through alias_of (sprite-sheet-optimize
stores one copy of a repeated frame; several names may point at that copy) are one
region, not an overlap. Warnings: fully
transparent frame, frames closer than --padding px (texture bleeding when filtered), trim metadata that
does not add up (spriteSourceSize vs frame vs sourceSize), non-power-of-two atlas, wasted area above --max-waste.
"""
import argparse, os, json, sys
import numpy as np
from PIL import Image


def frames_of(meta):
    f = meta["frames"]
    return [(k, v) for k, v in f.items()] if isinstance(f, dict) else [(v["filename"], v) for v in f]


def validate(meta, image, padding=1, max_waste=0.5):
    out, W, H = [], image.width, image.height
    add = lambda lvl, name, msg: out.append({"level": lvl, "frame": name, "msg": msg})
    fr = frames_of(meta); names = [n for n, _ in fr]
    for n in {n for n in names if names.count(n) > 1}: add("error", n, "duplicate frame name")
    a = np.array(image.convert("RGBA"))[..., 3]
    rects = []
    for n, v in fr:
        r = v["frame"]; x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        if x < 0 or y < 0 or x + w > W or y + h > H: add("error", n, f"frame {x},{y} {w}x{h} outside atlas {W}x{H}"); continue
        if w <= 0 or h <= 0: add("error", n, "zero-size frame"); continue
        rects.append((n, x, y, w, h, v))
        if not (a[y:y + h, x:x + w] > 0).any(): add("warn", n, "frame is fully transparent")
        s, o = v.get("spriteSourceSize"), v.get("sourceSize")
        if s and o:
            if (s["w"], s["h"]) != (w, h): add("warn", n, f"spriteSourceSize {s['w']}x{s['h']} != frame {w}x{h}")
            if s["x"] + s["w"] > o["w"] or s["y"] + s["h"] > o["h"]: add("warn", n, "trimmed frame does not fit inside sourceSize")
    by_name = {n: v for n, _, _, _, _, v in rects}

    def canon(name):
        seen = set()
        while name not in seen:
            seen.add(name)
            nxt = (by_name.get(name) or {}).get("alias_of")
            if not nxt:
                break
            name = nxt
        return name

    for i, (n1, x1, y1, w1, h1, v1) in enumerate(rects):
        for n2, x2, y2, w2, h2, v2 in rects[i + 1:]:
            gx = max(x1, x2) - min(x1 + w1, x2 + w2); gy = max(y1, y2) - min(y1 + h1, y2 + h2)     # negative = overlap on that axis
            if gx < 0 and gy < 0:
                same = (x1, y1, w1, h1) == (x2, y2, w2, h2)
                if same and canon(n1) == canon(n2):
                    continue
                add("error", n1, f"overlaps {n2}")
            else:
                gap = gy if gx < 0 else gx if gy < 0 else max(gx, gy)    # distance between the nearest facing edges
                if gap < padding: add("warn", n1, f"only {gap}px from {n2} (padding {padding})")
    if (W & (W - 1)) or (H & (H - 1)): out.append({"level": "warn", "frame": "", "msg": f"atlas {W}x{H} is not power-of-two"})
    used = sum(w * h for _, _, _, w, h, _ in rects)
    if W * H and 1 - used / (W * H) > max_waste: out.append({"level": "warn", "frame": "", "msg": f"{1 - used / (W * H):.0%} of the atlas is unused"})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate an atlas JSON against its PNG.")
    ap.add_argument("json"); ap.add_argument("--image"); ap.add_argument("--padding", type=int, default=1)
    ap.add_argument("--max-waste", type=float, default=0.5); ap.add_argument("--strict", action="store_true")
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
    _src_keys = ('json', 'image')
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

    meta = json.load(open(a.json)); img = a.image or os.path.join(os.path.dirname(os.path.abspath(a.json)), meta["meta"]["image"])
    if not os.path.exists(img): sys.exit(f"ERROR atlas image not found: {img}")
    res = validate(meta, Image.open(img), a.padding, a.max_waste)
    for r in res: print(f"{r['level'].upper():5} {r['frame'] or '-'}: {r['msg']}")
    e = sum(r["level"] == "error" for r in res); w = len(res) - e
    print(f"{len(frames_of(meta))} frame(s): {e} error(s), {w} warning(s)")
    return 1 if e or (a.strict and w) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
