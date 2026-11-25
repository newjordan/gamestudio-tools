#!/usr/bin/env python3
"""nav-to-godot: write a Godot 4 NavigationRegion2D scene from a Tiled map's walkability.

Uses the same walkable-grid rules as map-reach / nav-grid, merges walkable tiles
into rectangles (tile-colliders), cuts partly covered cells, then merges those
cut pieces with neighbouring walkable rectangles so the navmesh has fewer
outlines, and writes each rectangle as a NavigationPolygon outline in pixel
coordinates (layout verified against official Godot 4.7.2). Solids can also
come from tile-colliders output
(`--colliders FILE`, or a `<map stem>.colliders.json` sitting next to the map).
The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, math, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-to-godot"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-reach"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-colliders"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402
import gst_read  # noqa: E402
import godot_text  # noqa: E402
import map_to_godot  # noqa: E402
import map_reach  # noqa: E402
import tile_colliders  # noqa: E402


def collider_candidates(map_path):
    """File names, next to the map, that count as 'the colliders for this map'."""
    folder = os.path.dirname(os.path.abspath(map_path))
    stem = os.path.splitext(os.path.basename(map_path))[0]
    return [os.path.join(folder, stem + suffix) for suffix in (".colliders.json", "_colliders.json", "-colliders.json")]


def find_colliders(map_path):
    for cand in collider_candidates(map_path):
        if os.path.isfile(cand):
            return cand
    return None


def _num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise GstInputError("collider %s is not a finite number" % what)
    return float(v)


def collider_rects(path, tw, th):
    """[(x, y, w, h)] pixel rectangles from tile-colliders output (zero-size ones dropped).

    Accepts the default JSON (`{"tile": [tw, th], "rects": [{x, y, w, h}, ...]}`) and the
    `--tiled-objects` output (`{"type": "objectgroup", "objects": [{x, y, width, height}, ...]}`).
    """
    doc = gst_read.load_json(path, "colliders JSON")
    if not isinstance(doc, dict):
        raise GstInputError("colliders file must be a JSON object (tile-colliders output)")
    if isinstance(doc.get("rects"), list):
        items = [(r.get("x"), r.get("y"), r.get("w"), r.get("h")) if isinstance(r, dict) else (None,) * 4
                 for r in doc["rects"]]
        tile = doc.get("tile")
        if tile is not None:
            if (not isinstance(tile, list) or len(tile) != 2
                    or not all(isinstance(n, int) and not isinstance(n, bool) for n in tile)):
                raise GstInputError("colliders file has a malformed tile size")
            if (tile[0], tile[1]) != (tw, th):
                raise GstInputError("colliders were made for %dx%d tiles but the map uses %dx%d" % (tile[0], tile[1], tw, th))
    elif isinstance(doc.get("objects"), list):
        items = [(o.get("x"), o.get("y"), o.get("width"), o.get("height")) if isinstance(o, dict) else (None,) * 4
                 for o in doc["objects"]]
    else:
        raise GstInputError("colliders file has no `rects` or `objects` list (expected tile-colliders output)")
    out = []
    for x, y, w, h in items:
        x, y, w, h = _num(x, "x"), _num(y, "y"), _num(w, "width"), _num(h, "height")
        if w > 0 and h > 0:
            out.append((x, y, w, h))
    return out


def blocked_from_rects(rects, tw, th, cols, rows):
    """Boolean (rows, cols) grid of cells whose interior any rectangle overlaps (whole-cell blocking)."""
    blocked = np.zeros((rows, cols), bool)
    for x, y, w, h in rects:
        tx0, tx1 = max(0, math.floor(x / tw)), min(cols, math.ceil((x + w) / tw))
        ty0, ty1 = max(0, math.floor(y / th)), min(rows, math.ceil((y + h) / th))
        if tx1 > tx0 and ty1 > ty0:
            blocked[ty0:ty1, tx0:tx1] = True
    return blocked


def blocked_from_colliders(path, tw, th, cols, rows):
    """Cells covered by tile-colliders output, a cell being blocked when a rectangle overlaps its interior."""
    return blocked_from_rects(collider_rects(path, tw, th), tw, th, cols, rows)


EPS = 1e-6
MAX_CUTS_PER_CELL = 64        # a cell crossed by more colliders than this is blocked whole rather than cut
MIN_PIECE = 1.0               # default: free pieces thinner than this many pixels are dropped


def _cell_pieces(cx0, cy0, cx1, cy1, clips, min_piece):
    """Free axis-aligned pieces of one cell after removing `clips` (rectangles clipped to the cell).

    Exact: the cell is split along every clip edge, elementary boxes are free when no clip covers them,
    and free boxes are merged into rectangles. Returns (pieces, dropped_slivers).
    """
    xs = sorted({cx0, cx1, *(c[0] for c in clips), *(c[2] for c in clips)})
    ys = sorted({cy0, cy1, *(c[1] for c in clips), *(c[3] for c in clips)})
    grid = []
    for j in range(len(ys) - 1):
        my = (ys[j] + ys[j + 1]) / 2.0
        row = []
        for i in range(len(xs) - 1):
            mx = (xs[i] + xs[i + 1]) / 2.0
            row.append(not any(c[0] <= mx <= c[2] and c[1] <= my <= c[3] for c in clips))
        grid.append(row)
    pieces, dropped = [], 0
    for ix, iy, iw, ih in tile_colliders.merge(grid):
        x0, y0, x1, y1 = xs[ix], ys[iy], xs[ix + iw], ys[iy + ih]
        if x1 - x0 < min_piece or y1 - y0 < min_piece:
            dropped += 1
            continue
        pieces.append((x0, y0, x1, y1))
    return pieces, dropped


def cut_walk(walk, rects, tw, th, min_piece=MIN_PIECE):
    """Remove collider rectangles from a walkable grid, cutting partly covered cells instead of blocking them.

    Returns (clean_grid, pieces, stats). `clean_grid` keeps only cells no collider touches; `pieces` are the
    free rectangles (x0, y0, x1, y1) left inside cells a collider only partly covers.
    """
    rows, cols = walk.shape
    clips_by_cell = {}
    for x, y, w, h in rects:
        tx0, tx1 = max(0, math.floor((x + EPS) / tw)), min(cols, math.ceil((x + w - EPS) / tw))
        ty0, ty1 = max(0, math.floor((y + EPS) / th)), min(rows, math.ceil((y + h - EPS) / th))
        for ty in range(ty0, ty1):
            for tx in range(tx0, tx1):
                if not walk[ty, tx]:
                    continue
                cx0, cy0 = tx * tw, ty * th
                clip = (max(x, cx0), max(y, cy0), min(x + w, cx0 + tw), min(y + h, cy0 + th))
                if clip[2] - clip[0] > EPS and clip[3] - clip[1] > EPS:
                    clips_by_cell.setdefault((tx, ty), []).append(clip)
    clean = walk.copy()
    pieces, stats = [], {"cut_cells": 0, "blocked_cells": 0, "dropped_slivers": 0, "overflow_cells": 0}
    for (tx, ty), clips in sorted(clips_by_cell.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        clean[ty, tx] = False
        cx0, cy0, cx1, cy1 = tx * tw, ty * th, (tx + 1) * tw, (ty + 1) * th
        if len(clips) > MAX_CUTS_PER_CELL:
            stats["overflow_cells"] += 1
            stats["blocked_cells"] += 1
            continue
        got, dropped = _cell_pieces(cx0, cy0, cx1, cy1, clips, min_piece)
        stats["dropped_slivers"] += dropped
        if got:
            pieces.extend(got)
            stats["cut_cells"] += 1
        else:
            stats["blocked_cells"] += 1
    return clean, pieces, stats


MAX_MERGE_EDGES = 2048        # if a cut has more distinct edges than this, skip the global merge


def _unique_edges(vals, eps=EPS):
    out = []
    for v in sorted(vals):
        if not out or v - out[-1] > eps:
            out.append(v)
    return out


def _edge_index(edges, v):
    # the uniquing pass already collapsed values within EPS of each other
    lo, hi = 0, len(edges) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if edges[mid] < v - EPS:
            lo = mid + 1
        else:
            hi = mid
    return lo


def merge_rects(rects, max_edges=MAX_MERGE_EDGES):
    """Merge axis-aligned rectangles that share an edge into larger rectangles.

    Coverage is unchanged (a partition of the same union). If there are too
    many distinct edges to build a grid safely, the input is returned as-is
    and the second return value is False.
    """
    boxes = [(float(x0), float(y0), float(x1), float(y1))
             for x0, y0, x1, y1 in rects if (x1 - x0) > EPS and (y1 - y0) > EPS]
    if len(boxes) <= 1:
        return list(boxes), True
    xs = _unique_edges([b[0] for b in boxes] + [b[2] for b in boxes])
    ys = _unique_edges([b[1] for b in boxes] + [b[3] for b in boxes])
    if len(xs) > max_edges or len(ys) > max_edges:
        return list(boxes), False
    grid = [[False] * (len(xs) - 1) for _ in range(len(ys) - 1)]
    for x0, y0, x1, y1 in boxes:
        ix0, ix1 = _edge_index(xs, x0), _edge_index(xs, x1)
        iy0, iy1 = _edge_index(ys, y0), _edge_index(ys, y1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        for iy in range(iy0, iy1):
            row = grid[iy]
            for ix in range(ix0, ix1):
                row[ix] = True
    merged = []
    for ix, iy, iw, ih in tile_colliders.merge(grid):
        merged.append((xs[ix], ys[iy], xs[ix + iw], ys[iy + ih]))
    return merged, True


def outlines_from_walk(walk, tw, th):
    if hasattr(walk, "tolist"):
        grid = walk.astype(bool).tolist()
    else:
        grid = [list(row) for row in walk]
    if not grid or not grid[0]:
        return []
    rects = tile_colliders.merge(grid)  # (tx, ty, tw_tiles, th_tiles)
    outs = []
    for tx, ty, rw, rh in rects:
        x0, y0 = tx * tw, ty * th
        x1, y1 = (tx + rw) * tw, (ty + rh) * th
        outs.append((x0, y0, x1, y1))
    return outs


def write_scene(path, rects):
    if not rects:
        raise GstInputError("Tiled map has no walkable tiles")
    verts = []
    polys = []
    outlines = []
    for x0, y0, x1, y1 in rects:
        base = len(verts)
        verts.extend([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
        polys.append((base, base + 1, base + 2, base + 3))
        outlines.append((x0, y0, x1, y0, x1, y1, x0, y1))
    def _n(v):
        v = float(v)
        return str(int(v)) if v == int(v) else ("%.9f" % v).rstrip("0").rstrip(".")
    def pva(pairs):
        return "PackedVector2Array(" + ", ".join("%s, %s" % (x, y) for x, y in pairs) + ")"
    def pia(idx):
        return "PackedInt32Array(" + ", ".join(str(i) for i in idx) + ")"
    vert_lit = "PackedVector2Array(" + ", ".join("%s, %s" % (_n(v[0]), _n(v[1])) for v in verts) + ")"
    poly_lit = "Array[PackedInt32Array]([%s])" % ", ".join(pia(p) for p in polys)
    out_lit = "Array[PackedVector2Array]([%s])" % ", ".join(
        "PackedVector2Array(" + ", ".join(_n(n) for n in o) + ")" for o in outlines
    )
    lines = [
        "[gd_scene load_steps=2 format=3]",
        "",
        '[sub_resource type="NavigationPolygon" id="NavigationPolygon_0"]',
        "vertices = %s" % vert_lit,
        "polygons = %s" % poly_lit,
        "outlines = %s" % out_lit,
        "",
        '[node name="Nav" type="NavigationRegion2D"]',
        'navigation_polygon = SubResource("NavigationPolygon_0")',
        "",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    return len(rects)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 NavigationRegion2D scene from a Tiled map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True, help="output .tscn")
    ap.add_argument("--solid-layer", help="tile layer whose non-empty (or listed) tiles are solid")
    ap.add_argument("--solid-ids", help="comma-separated Tiled GIDs treated as solid")
    ap.add_argument("--ground-layer", help="a cell must have a tile on this layer to be walkable")
    ap.add_argument("--colliders", metavar="FILE",
                    help="tile-colliders output (rects JSON or --tiled-objects); its cells are solid. "
                         "Without --solid-layer/--solid-ids, a <map stem>.colliders.json next to the map is used")
    ap.add_argument("--block-whole-cells", action="store_true",
                    help="block every cell a collider touches (the 2.1.0 behaviour) instead of cutting partly covered cells")
    ap.add_argument("--min-piece", type=float, default=MIN_PIECE, metavar="PX",
                    help="drop free pieces thinner than PX pixels left by a cut (default %g)" % MIN_PIECE)
    ap.add_argument("--no-colliders", action="store_true", help="do not pick up a sibling colliders file")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    doc = map_to_godot.load_map(a.map)
    tw, th = int(doc.get("tilewidth") or 16), int(doc.get("tileheight") or 16)
    solid_ids = ()
    if a.solid_ids:
        solid_ids = tuple(int(s.strip()) for s in a.solid_ids.split(",") if s.strip())
    try:
        walk = map_reach.walkable_grid(doc, solid_layer=a.solid_layer, solid_ids=solid_ids, ground_layer=a.ground_layer)
    except SystemExit as e:
        raise GstInputError("cannot build walkable grid: %s" % (e.code if e.code is not None else e)) from e
    except Exception as e:
        raise GstInputError("cannot build walkable grid: %s" % e) from e
    colliders, source = a.colliders, "flag"
    if not colliders and not a.no_colliders and not a.solid_layer and not a.solid_ids:
        colliders, source = find_colliders(a.map), "auto"
    cut = {"cut_cells": 0, "blocked_cells": 0, "dropped_slivers": 0, "overflow_cells": 0}
    pieces = []
    if colliders:
        safe_out.check(colliders, a.out, a.in_place)
        rows, cols = walk.shape
        crects = collider_rects(colliders, tw, th)
        if a.block_whole_cells:
            try:
                walk = walk & ~blocked_from_rects(crects, tw, th, cols, rows)
            except (OverflowError, ValueError) as e:
                raise GstInputError("colliders have a value too large to place on the map (%s)" % e) from e
        else:
            if not math.isfinite(a.min_piece) or a.min_piece < 0:
                raise GstInputError("--min-piece must be a non-negative number")
            try:
                walk, pieces, cut = cut_walk(walk, crects, tw, th, a.min_piece)
            except (OverflowError, ValueError, ZeroDivisionError) as e:
                raise GstInputError("colliders have a value too large to place on the map (%s)" % e) from e
    else:
        source = None
    raw = outlines_from_walk(walk, tw, th) + pieces
    rects, merged_ok = merge_rects(raw)
    n = write_scene(a.out, rects)
    rec = {"out": a.out, "rects": n, "colliders": colliders or None, "colliders_source": source, "walkable": int(walk.sum()) if hasattr(walk, "sum") else sum(sum(row) for row in walk),
           "cut_cells": cut["cut_cells"], "cut_pieces": len(pieces), "blocked_cells": cut["blocked_cells"],
           "dropped_slivers": cut["dropped_slivers"], "overflow_cells": cut["overflow_cells"],
           "rects_before_merge": len(raw), "merged": merged_ok}
    extra_cut = (", %d cell(s) cut into %d piece(s)" % (cut["cut_cells"], len(pieces))) if pieces else ""
    extra_merge = (", %d region(s) after merge" % n) if pieces and n != len(raw) else ""
    print("%d walkable region(s) -> %s%s" % (n, a.out, (" (solids from %s%s%s)" % (os.path.basename(colliders), extra_cut, extra_merge)) if colliders else ""))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
