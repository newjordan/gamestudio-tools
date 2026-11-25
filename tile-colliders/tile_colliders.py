#!/usr/bin/env python3
"""tile-colliders: merge solid tiles of a Tiled-style map into the fewest axis-aligned rectangles
(greedy: horizontal runs, then stack identical runs vertically) and export them as JSON (pixels + tiles)
or a Tiled object layer. Far fewer collision shapes than one box per tile, which keeps physics cheap.
"""
import os
import argparse, json
import sys


def solid_grid(m, solid_ids, layer=None):
    layers = [l for l in m["layers"] if l["type"] == "tilelayer"]
    l = next(x for x in layers if x["name"] == layer) if layer else layers[0]
    w, h = l["width"], l["height"]
    ids = set(solid_ids) if solid_ids else None
    return [[(((v & 0x1FFFFFFF) in ids) if ids else (v & 0x1FFFFFFF) != 0) for v in l["data"][y * w:(y + 1) * w]] for y in range(h)]


def merge(grid):
    h, w = len(grid), len(grid[0])
    runs = []
    for y in range(h):
        x = 0
        while x < w:
            if grid[y][x]:
                s = x
                while x < w and grid[y][x]: x += 1
                runs.append((s, y, x - s))
            else:
                x += 1
    open_, out = {}, []
    by_row = {}
    for s, y, n in runs: by_row.setdefault(y, []).append((s, n))
    for y in range(h):
        nxt = {}
        for (s, n) in by_row.get(y, []):
            if (s, n) in open_:
                nxt[(s, n)] = open_[(s, n)]; nxt[(s, n)][3] += 1
            else:
                nxt[(s, n)] = [s, y, n, 1]
        for key, rect in open_.items():
            if key not in nxt: out.append(tuple(rect))
        open_ = nxt
    out += [tuple(r) for r in open_.values()]
    return sorted(out, key=lambda r: (r[1], r[0]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge solid tiles into collision rectangles.")
    ap.add_argument("map")
    ap.add_argument("--solid", help="comma list of solid tile ids (default: every non-empty tile)")
    ap.add_argument("--layer")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tiled-objects", action="store_true", help="write a Tiled object-layer JSON instead")
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
    _src_keys = ('map',)
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

    m = json.load(open(a.map))
    tw, th = m["tilewidth"], m["tileheight"]
    g = solid_grid(m, [int(x) for x in a.solid.split(",")] if a.solid else None, a.layer)
    rects = merge(g)
    n_tiles = sum(map(sum, g))
    if a.tiled_objects:
        out = {"type": "objectgroup", "name": "collision", "objects": [
            {"id": i + 1, "x": x * tw, "y": y * th, "width": w * tw, "height": h * th, "rotation": 0, "visible": True, "type": "", "name": ""}
            for i, (x, y, w, h) in enumerate(rects)]}
    else:
        out = {"tile": [tw, th], "rects": [{"x": x * tw, "y": y * th, "w": w * tw, "h": h * th, "tx": x, "ty": y, "tw": w, "th": h} for x, y, w, h in rects]}
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"{n_tiles} solid tile(s) -> {len(rects)} rectangle(s) in {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
