#!/usr/bin/env python3
"""tilemap-stats: per-layer and per-tileset statistics for Tiled JSON maps, for level QA dashboards and CI.
For each map: size and orientation, per tile layer the empty ratio, unique tile ids, flip counts and the most-used
tiles, per object layer the object counts by type (or class) and by name, tilesets that are never used, and layers that
are empty or hidden. Group layers are flattened by path (as in map-diff). Finite and infinite maps are supported;
tile data may be a plain array or a base64 string (zlib, gzip or zstd). Text, JSON and CSV output;
--fail-on-empty-layer, --fail-on-hidden and --fail-on-unused-tileset give CI exit codes.
"""
import argparse, os, csv, json, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLIPS = 0xE0000000


def gids_of(l):
    if l.get("type") != "tilelayer": return []
    if "chunks" in l: return [g for c in l["chunks"] for g in map_diff.layer_gids(l, c)]
    return map_diff.layer_gids(l)


def stats_one(path, m):
    w, h = m.get("width", 0), m.get("height", 0)
    layers = list(map_diff.flat_layers(m.get("layers", [])))
    tilesets = m.get("tilesets", [])
    ranges = []
    for i, ts in enumerate(tilesets):
        fg = ts.get("firstgid", 1); nxt = tilesets[i + 1]["firstgid"] if i + 1 < len(tilesets) else fg + ts.get("tilecount", 10 ** 9)
        ranges.append((ts.get("name") or ts.get("source") or f"tileset@{fg}", fg, nxt, ts))
    used_gids = Counter(); tile_layers, obj_layers, empty_layers, hidden_layers = [], [], [], []
    for name, l in layers:
        typ = l.get("type", "")
        if typ == "tilelayer":
            gids = gids_of(l); n = len(gids); empty = sum(1 for g in gids if not (g & MASK)); flipped = sum(1 for g in gids if g & FLIPS)
            ids = Counter(g & MASK for g in gids if g & MASK)
            used_gids.update(ids)
            rec = {"name": name, "type": typ, "visible": l.get("visible", True), "opacity": l.get("opacity", 1), "cells": n,
                   "empty": empty, "empty_ratio": round(empty / n, 4) if n else 1.0, "unique_tiles": len(ids), "flipped": flipped,
                   "most_used": [[int(k), int(v)] for k, v in ids.most_common(8)]}
            tile_layers.append(rec)
            if n == 0 or empty == n: empty_layers.append(name)
        elif typ == "objectgroup":
            objs = l.get("objects", []); by_type, by_name = Counter(), Counter()
            for o in objs:
                by_type[o.get("type") or o.get("class") or ""] += 1; by_name[o.get("name") or ""] += 1
            rec = {"name": name, "type": typ, "visible": l.get("visible", True), "objects": len(objs),
                   "by_type": dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))), "by_name": dict(sorted((k, v) for k, v in by_name.items() if k))}
            obj_layers.append(rec)
            if not objs: empty_layers.append(name)
        elif typ == "imagelayer":
            if not l.get("image"): empty_layers.append(name)
        if l.get("visible", True) is False: hidden_layers.append(name)
    ts_stats, unused_ts = [], []
    for name, fg, nxt, ts in ranges:
        used = {g: n for g, n in used_gids.items() if fg <= g < nxt}
        rec = {"name": name, "firstgid": fg, "tilecount": ts.get("tilecount"), "unique_used": len(used), "uses": int(sum(used.values()))}
        ts_stats.append(rec)
        if rec["uses"] == 0: unused_ts.append(name)
    return {"file": os.path.basename(path), "width": w, "height": h, "tilewidth": m.get("tilewidth"), "tileheight": m.get("tileheight"),
            "orientation": m.get("orientation", "orthogonal"), "infinite": bool(m.get("infinite")), "cells": w * h,
            "tile_layers": tile_layers, "object_layers": obj_layers, "tilesets": ts_stats, "empty_layers": empty_layers,
            "hidden_layers": hidden_layers, "unused_tilesets": unused_ts, "objects": sum(o["objects"] for o in obj_layers)}


def lines(s):
    L = [f"{s['file']}: {s['width']}x{s['height']} {s['orientation']}" + (" infinite" if s["infinite"] else "") + f", {len(s['tile_layers'])} tile layer(s), {s['objects']} object(s)"]
    for t in s["tile_layers"]:
        L.append(f"  tile {t['name']}: {t['cells']} cells, {t['empty_ratio'] * 100:.0f}% empty, {t['unique_tiles']} unique, {t['flipped']} flipped" + ("" if t["visible"] else " (hidden)"))
    for o in s["object_layers"]:
        types = ", ".join(f"{k or '(no type)'} x{v}" for k, v in list(o["by_type"].items())[:8])
        L.append(f"  objects {o['name']}: {o['objects']}" + (f" ({types})" if types else "") + ("" if o["visible"] else " (hidden)"))
    for t in s["tilesets"]:
        L.append(f"  tileset {t['name']}: {t['unique_used']} unique tile(s), {t['uses']} use(s)" + (" UNUSED" if t["uses"] == 0 else ""))
    if s["empty_layers"]: L.append("  empty layers: " + ", ".join(s["empty_layers"]))
    if s["hidden_layers"]: L.append("  hidden layers: " + ", ".join(s["hidden_layers"]))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="Statistics for Tiled JSON maps.")
    ap.add_argument("maps", nargs="+"); ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--fail-on-empty-layer", action="store_true"); ap.add_argument("--fail-on-hidden", action="store_true"); ap.add_argument("--fail-on-unused-tileset", action="store_true")
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
    _src_keys = ('maps',)
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

    rows = [stats_one(p, json.load(open(p))) for p in a.maps]
    for s in rows:
        print("\n".join(lines(s)))
    if a.json: json.dump(rows if len(rows) > 1 else rows[0], open(a.json, "w"), indent=1)
    if a.csv:
        cols = ["file", "width", "height", "orientation", "infinite", "objects", "empty_layers", "hidden_layers", "unused_tilesets"]
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
            for s in rows:
                w.writerow({k: (";".join(s[k]) if isinstance(s.get(k), list) else s.get(k)) for k in cols})
    bad = any((a.fail_on_empty_layer and s["empty_layers"]) or (a.fail_on_hidden and s["hidden_layers"]) or (a.fail_on_unused_tileset and s["unused_tilesets"]) for s in rows)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
