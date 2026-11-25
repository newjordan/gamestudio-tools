#!/usr/bin/env python3
"""map-reach: can the player actually get there? Flood-fills a Tiled JSON map (top-down, finite) from a start tile over walkable
cells and reports which walkable regions and which objects (doors, keys, chests, exits ...) are unreachable.
Walkable cells are defined by --solid-layer NAME (any non-empty tile there blocks) and/or --solid-ids 3,4,5 (those tile ids block on
every tile layer, or on --ground-layer only) and optionally --ground-layer NAME (a cell must have a tile there to be walkable).
Start: --start X,Y (tile coordinates) or the first object named/typed --start-name (default "spawn,start,player_start"). Objects are
reached when their tile (point, rectangle centre; tile objects use their bottom-left) is a reachable cell, or - with --adjacent -
when a neighbour is (for doors and chests that sit on solid tiles). 4-way movement unless --diagonal (no corner cutting).
Output: a text report, --json, and --png (reachable cells green, walkable-but-cut-off red, solid dark, objects as dots).
Exit 1 when a --require type has an unreachable object or --fail-on-islands finds cut-off walkable areas of --min-island tiles or more.
Platformer reachability (jump arcs) is NOT modelled.
"""
import argparse, os, json, sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

MASK = 0x0FFFFFFF


def tile_layers(layers):
    for l in layers:
        if l.get("type") == "group": yield from tile_layers(l.get("layers", []))
        elif l.get("type") == "tilelayer": yield l


def object_layers(layers):
    for l in layers:
        if l.get("type") == "group": yield from object_layers(l.get("layers", []))
        elif l.get("type") == "objectgroup": yield l


def grid_of(l, w, h):
    d = l.get("data", [])
    if isinstance(d, str) or "chunks" in l: raise SystemExit(f"layer {l.get('name')!r}: only finite maps with plain array data are supported")
    return (np.array(d, dtype=np.int64) & MASK).reshape(h, w)


def walkable_grid(m, solid_layer=None, solid_ids=(), ground_layer=None):
    w, h = m["width"], m["height"]; walk = np.ones((h, w), bool); layers = list(tile_layers(m["layers"]))
    if m.get("infinite"): raise SystemExit("infinite maps are not supported")
    names = {l["name"] for l in layers}
    for n in (solid_layer, ground_layer):
        if n and n not in names: raise SystemExit(f"tile layer {n!r} not found (have: {', '.join(sorted(names))})")
    if ground_layer: walk &= grid_of(next(l for l in layers if l["name"] == ground_layer), w, h) != 0
    if solid_layer: walk &= grid_of(next(l for l in layers if l["name"] == solid_layer), w, h) == 0
    if solid_ids:
        ids = set(solid_ids)
        for l in layers:
            if ground_layer and l["name"] != ground_layer: continue
            walk &= ~np.isin(grid_of(l, w, h), list(ids))
    return walk


def flood(walk, start, diagonal=False):
    h, w = walk.shape; seen = np.zeros_like(walk); sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h) or not walk[sy, sx]: raise SystemExit(f"start tile {start} is not a walkable cell")
    q = deque([(sx, sy)]); seen[sy, sx] = True
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diagonal else [])
    while q:
        x, y = q.popleft()
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and walk[ny, nx] and not seen[ny, nx]:
                if dx and dy and not (walk[y, nx] and walk[ny, x]): continue          # no cutting corners
                seen[ny, nx] = True; q.append((nx, ny))
    return seen


def islands(walk, seen, diagonal=False):
    h, w = walk.shape; rest = walk & ~seen; mark = np.zeros_like(walk); out = []
    for y in range(h):
        for x in range(w):
            if rest[y, x] and not mark[y, x]:
                comp = flood_from(rest, (x, y), diagonal); mark |= comp; ys, xs = np.where(comp)
                out.append({"tiles": int(comp.sum()), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]})
    return sorted(out, key=lambda i: -i["tiles"])


def flood_from(mask, start, diagonal):
    return flood(mask, start, diagonal)


def object_tile(o, tw, th):
    x, y = o.get("x", 0), o.get("y", 0)
    if "gid" in o: return int(x // tw), int((y - 1) // th)                     # tile objects: origin bottom-left
    if o.get("point") or not o.get("width"): return int(x // tw), int(y // th)
    return int((x + o["width"] / 2) // tw), int((y + o["height"] / 2) // th)


def find_start(m, names):
    names = [n.strip().lower() for n in names.split(",")]; tw, th = m["tilewidth"], m["tileheight"]
    for l in object_layers(m["layers"]):
        for o in l.get("objects", []):
            if (o.get("name", "").lower() in names) or ((o.get("type") or o.get("class") or "").lower() in names): return object_tile(o, tw, th), o.get("name") or o.get("type")
    return None, None


def analyze(m, start=None, start_name="spawn,start,player_start", solid_layer=None, solid_ids=(), ground_layer=None, diagonal=False, adjacent=False, require=(), min_island=1):
    walk = walkable_grid(m, solid_layer, solid_ids, ground_layer); tw, th = m["tilewidth"], m["tileheight"]; src = None
    if start is None:
        start, src = find_start(m, start_name)
        if start is None: raise SystemExit(f"no start given and no object named {start_name!r} found; use --start X,Y")
    seen = flood(walk, start, diagonal); isl = [i for i in islands(walk, seen, diagonal) if i["tiles"] >= min_island]; h, w = walk.shape
    objs = []
    for l in object_layers(m["layers"]):
        for o in l.get("objects", []):
            tx, ty = object_tile(o, tw, th); inside = 0 <= tx < w and 0 <= ty < h
            direct = bool(inside and seen[ty, tx]); adj = False
            if adjacent and inside and not direct:
                adj = any(0 <= tx + dx < w and 0 <= ty + dy < h and seen[ty + dy, tx + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            objs.append({"id": o.get("id"), "name": o.get("name", ""), "type": o.get("type") or o.get("class") or "", "layer": l.get("name"), "tile": [tx, ty], "inside_map": inside,
                         "reachable": direct or adj, "on_solid": bool(inside and not walk[ty, tx])})
    req = {r.strip().lower() for r in require if r.strip()}
    bad = [o for o in objs if not o["reachable"] and (o["type"].lower() in req or o["name"].lower() in req)]
    return {"start": list(start), "start_from": src, "walkable": int(walk.sum()), "reachable": int(seen.sum()), "islands": isl, "objects": objs, "required_unreachable": bad}, walk, seen


def render(m, walk, seen, rep, scale=8):
    h, w = walk.shape; im = np.zeros((h, w, 3), np.uint8); im[:] = (40, 40, 48)
    im[walk & seen] = (60, 170, 80); im[walk & ~seen] = (200, 60, 60)
    img = Image.fromarray(im).resize((w * scale, h * scale), Image.NEAREST); d = ImageDraw.Draw(img)
    for o in rep["objects"]:
        if not o["inside_map"]: continue
        x, y = o["tile"]; c = (255, 255, 255) if o["reachable"] else (255, 220, 0); r = max(2, scale // 3)
        d.ellipse((x * scale + scale // 2 - r, y * scale + scale // 2 - r, x * scale + scale // 2 + r, y * scale + scale // 2 + r), fill=c, outline=(0, 0, 0))
    sx, sy = rep["start"]; d.rectangle((sx * scale, sy * scale, sx * scale + scale - 1, sy * scale + scale - 1), outline=(80, 160, 255), width=max(1, scale // 6))
    return img


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reachability check for Tiled maps (top-down).")
    ap.add_argument("map"); ap.add_argument("--start", help="start tile X,Y"); ap.add_argument("--start-name", default="spawn,start,player_start")
    ap.add_argument("--solid-layer"); ap.add_argument("--solid-ids", default=""); ap.add_argument("--ground-layer"); ap.add_argument("--diagonal", action="store_true"); ap.add_argument("--adjacent", action="store_true", help="an object counts as reached from a neighbouring reachable cell")
    ap.add_argument("--require", default="", help="comma list of object types/names that must be reachable"); ap.add_argument("--fail-on-islands", action="store_true"); ap.add_argument("--min-island", type=int, default=1)
    ap.add_argument("--json"); ap.add_argument("--png"); ap.add_argument("--scale", type=int, default=8)
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

    m = json.load(open(a.map)); start = tuple(int(v) for v in a.start.split(",")) if a.start else None
    rep, walk, seen = analyze(m, start, a.start_name, a.solid_layer, [int(x) for x in a.solid_ids.split(",") if x], a.ground_layer, a.diagonal, a.adjacent, a.require.split(","), a.min_island)
    print(f"start {tuple(rep['start'])}{' (' + rep['start_from'] + ')' if rep['start_from'] else ''}: {rep['reachable']} of {rep['walkable']} walkable tiles reachable, {len(rep['islands'])} cut-off area(s)")
    for i in rep["islands"][:10]: print(f"  island: {i['tiles']} tiles at {i['bbox']}")
    un = [o for o in rep["objects"] if not o["reachable"]]
    for o in un: print(f"  unreachable: {o['type'] or '-'} {o['name']!r} #{o['id']} at tile {tuple(o['tile'])}" + (" (on a solid tile)" if o["on_solid"] else "") + ("" if o["inside_map"] else " (outside the map)"))
    print(f"{len(rep['objects']) - len(un)} of {len(rep['objects'])} object(s) reachable")
    if a.json: json.dump(rep, open(a.json, "w"), indent=1)
    if a.png: render(m, walk, seen, rep, a.scale).save(a.png)
    return 1 if rep["required_unreachable"] or (a.fail_on_islands and rep["islands"]) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
