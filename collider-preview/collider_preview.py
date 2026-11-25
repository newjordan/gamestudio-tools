#!/usr/bin/env python3
"""collider-preview: see the collision shapes before the physics engine does. Draws tile-colliders output ({"tile": [w, h], "rects":
[{"x", "y", "w", "h"}]} in pixels) or a Tiled object layer / layer-with-objects export (objects with x, y, width, height) on top of the
rendered Tiled map (tile-preview) or on a plain background, with translucent fill, outline, optional index labels, and a coverage
report: shape count, covered area, share of the map, and shapes that overlap each other or run outside the map. Rectangles only.
"""
import argparse, os, json, sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-preview"))
import tile_preview  # noqa: E402


def load_rects(path):
    d = json.load(open(path))
    if isinstance(d, dict) and "rects" in d: return [(r["x"], r["y"], r["w"], r["h"]) for r in d["rects"]]
    objs = d.get("objects") if isinstance(d, dict) else None
    if objs is None and isinstance(d, dict) and "layers" in d: objs = [o for l in d["layers"] if l.get("type") == "objectgroup" for o in l.get("objects", [])]
    if objs is None: raise SystemExit("unrecognised collider file (want tile-colliders JSON, a Tiled object layer, or a map with object layers)")
    return [(o["x"], o["y"], o.get("width", 0), o.get("height", 0)) for o in objs if o.get("width") and o.get("height")]


def analyze(rects, size):
    W, H = size; area = sum(w * h for _, _, w, h in rects); outside = [i for i, (x, y, w, h) in enumerate(rects) if x < 0 or y < 0 or x + w > W or y + h > H]
    overlaps = []
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ax, ay, aw, ah = rects[i]; bx, by, bw, bh = rects[j]
            ix = min(ax + aw, bx + bw) - max(ax, bx); iy = min(ay + ah, by + bh) - max(ay, by)
            if ix > 0 and iy > 0: overlaps.append((i, j, ix * iy))
    return {"shapes": len(rects), "area_px": area, "map_px": W * H, "coverage": round(area / (W * H), 4) if W * H else 0.0, "outside": outside, "overlaps": [list(o) for o in overlaps]}


def draw(base, rects, scale=1, labels=False, color=(255, 40, 40)):
    im = base.convert("RGBA").resize((base.width * scale, base.height * scale), Image.NEAREST) if scale != 1 else base.convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i, (x, y, w, h) in enumerate(rects):
        box = (x * scale, y * scale, (x + w) * scale - 1, (y + h) * scale - 1); d.rectangle(box, fill=color + (70,), outline=color + (255,))
        if labels: d.text((box[0] + 2, box[1] + 1), str(i), fill=(255, 255, 255, 255))
    return Image.alpha_composite(im, ov)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draw collision rectangles over a Tiled map.")
    ap.add_argument("colliders"); ap.add_argument("--map", help="Tiled JSON map to render underneath (size and background)"); ap.add_argument("--tileset", help="tileset PNG for the map (see tile-preview)")
    ap.add_argument("--size", help="WxH pixels when there is no --map"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--labels", action="store_true"); ap.add_argument("--bg", default="#202830"); ap.add_argument("--fail-on-overlap", action="store_true"); ap.add_argument("--json")
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
    _src_keys = ('colliders', 'map')
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

    rects = load_rects(a.colliders)
    if a.map:
        m = json.load(open(a.map)); base, _ = tile_preview.render(m, a.tileset, os.path.dirname(os.path.abspath(a.map)))
        bg = Image.new("RGBA", base.size, tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)); base = Image.alpha_composite(bg, base.convert("RGBA"))
    elif a.size: w, h = (int(v) for v in a.size.lower().split("x")); base = Image.new("RGBA", (w, h), tuple(int(a.bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
    else: sys.exit("give --map or --size WxH")
    rep = analyze(rects, base.size); draw(base, rects, a.scale, a.labels).save(a.out)
    print(f"{rep['shapes']} shape(s) cover {rep['area_px']} of {rep['map_px']} px ({rep['coverage'] * 100:.1f}%); {len(rep['overlaps'])} overlapping pair(s), {len(rep['outside'])} outside the map -> {a.out}")
    if a.json: json.dump(rep, open(a.json, "w"), indent=1)
    return 1 if a.fail_on_overlap and (rep["overlaps"] or rep["outside"]) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
