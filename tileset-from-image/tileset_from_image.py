#!/usr/bin/env python3
"""tileset-from-image: slice a tileset PNG into tiles and audit it against the Tiled maps that use it: which tiles are
empty, which are exact visible-pixel duplicates of an earlier tile, how often each tile is used, and which are never used.
Maps are Tiled JSON (finite and infinite, nested groups; flip flags are masked off). The tileset is located in each map by
image file name (or by --firstgid, or the map's only tileset). Outputs a text report, optional JSON, and an annotated PNG:
unused tiles tinted red, duplicates outlined blue, empty tiles hatched grey. Exact duplicates only; for rotated/flipped
duplicates use tile-dedupe.
"""
import argparse, os, json, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-dedupe"))
import tile_dedupe  # noqa: E402

MASK = 0x0FFFFFFF


def iter_layers(layers):
    for l in layers:
        if l.get("type") == "group": yield from iter_layers(l.get("layers", []))
        else: yield l


def layer_gids(l):
    if l.get("type") != "tilelayer": return []
    if "chunks" in l: return [g for c in l["chunks"] for g in c.get("data", [])]
    d = l.get("data", [])
    if isinstance(d, str): raise SystemExit(f"layer {l.get('name')!r}: encoded tile data (base64/csv string) is not supported; export as JSON with plain arrays")
    return d


def find_firstgid(m, image_path, n_tiles, forced=None):
    if forced is not None: return forced, None
    base = os.path.basename(image_path).lower(); sets = m.get("tilesets", [])
    for ts in sets:
        if os.path.basename(ts.get("image", "")).lower() == base: return ts["firstgid"], None
    stem = os.path.splitext(base)[0]
    for ts in sets:
        if "image" not in ts and os.path.splitext(os.path.basename(ts.get("source", "")))[0].lower() == stem: return ts["firstgid"], None
    if len(sets) == 1: return sets[0]["firstgid"], f"assumed the map's only tileset ({sets[0].get('image') or sets[0].get('source')}) is {os.path.basename(image_path)}"
    return None, f"no tileset in this map matches {os.path.basename(image_path)}"


def audit(image_path, tile, maps, margin=0, spacing=0, forced_firstgid=None):
    img = Image.open(image_path).convert("RGBA")
    tiles, cols, rows = tile_dedupe.tiles_of(img, tile, margin, spacing)
    n = len(tiles); empty = [not (t[..., 3] > 0).any() for t in tiles]
    first, dups = {}, {}
    for i, t in enumerate(tiles):
        if empty[i]: continue
        k = tile_dedupe.key(t)
        if k in first: dups[i] = first[k]
        else: first[k] = i
    uses = np.zeros(n, int); per_map = {}; warnings = []
    for path, m in maps:
        fg, warn = find_firstgid(m, image_path, n, forced_firstgid)
        if warn: warnings.append(f"{os.path.basename(path)}: {warn}")
        if fg is None: continue
        c = 0
        for l in iter_layers(m.get("layers", [])):
            for g in layer_gids(l):
                g &= MASK
                if g >= fg and g - fg < n: uses[g - fg] += 1; c += 1
        per_map[os.path.basename(path)] = c
    return {"image": image_path, "tile": list(tile), "cols": cols, "rows": rows, "tiles": n, "empty": [i for i in range(n) if empty[i]],
            "duplicates": {str(k): v for k, v in dups.items()}, "uses": uses.tolist(), "per_map": per_map, "warnings": warnings,
            "unused": [i for i in range(n) if uses[i] == 0 and not empty[i]] if per_map else [], "maps": len(maps), "matched_maps": len(per_map)}, img


def annotate(img, rep, margin=0, spacing=0):
    out = img.copy().convert("RGBA"); tw, th = rep["tile"]; d = ImageDraw.Draw(out, "RGBA"); cols = rep["cols"]
    def box(i): c, r = i % cols, i // cols; x, y = margin + c * (tw + spacing), margin + r * (th + spacing); return (x, y, x + tw - 1, y + th - 1)
    if rep["matched_maps"]:
        for i in rep["unused"]: d.rectangle(box(i), fill=(255, 0, 0, 90))
    for i in rep["empty"]:
        x0, y0, x1, y1 = box(i)
        for k in range(-th, tw, 4): d.line((x0 + k, y1, x0 + k + th, y0), fill=(150, 150, 150, 160))
    for k in rep["duplicates"]: d.rectangle(box(int(k)), outline=(0, 110, 255, 255))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit a tileset image against the Tiled maps that use it.")
    ap.add_argument("tileset"); ap.add_argument("maps", nargs="*", help="Tiled JSON maps (optional; without maps only empties and duplicates are reported)")
    ap.add_argument("--tile", required=True, help="tile size WxH, e.g. 16x16 or 16"); ap.add_argument("--margin", type=int, default=0); ap.add_argument("--spacing", type=int, default=0)
    ap.add_argument("--firstgid", type=int, help="force the tileset's firstgid in every map"); ap.add_argument("--json"); ap.add_argument("--png", help="annotated output PNG")
    ap.add_argument("--fail-on-unused", action="store_true"); ap.add_argument("--fail-on-duplicates", action="store_true")
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
    _src_keys = ('tileset', 'maps')
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

    t = a.tile.lower().split("x"); tile = (int(t[0]), int(t[-1]))
    maps = [(p, json.load(open(p))) for p in a.maps]
    rep, img = audit(a.tileset, tile, maps, a.margin, a.spacing, a.firstgid)
    print(f"{rep['tiles']} tiles ({rep['cols']}x{rep['rows']}), {len(rep['empty'])} empty, {len(rep['duplicates'])} duplicate")
    for k, v in rep["duplicates"].items(): print(f"  dup: tile {k} == tile {v}")
    if maps and not rep["matched_maps"]:
        for w in rep["warnings"]: print("WARN " + w)
        print("ERROR no map uses this tileset (checked by image name; try --firstgid), so usage was not computed"); return 2
    if maps:
        print(f"used {rep['tiles'] - len(rep['empty']) - len(rep['unused'])} of {rep['tiles'] - len(rep['empty'])} non-empty tiles across {rep['matched_maps']} of {len(maps)} map(s); unused: {len(rep['unused'])}")
        if rep["unused"]: print("  unused: " + ", ".join(map(str, rep["unused"][:60])) + (" ..." if len(rep["unused"]) > 60 else ""))
        top = sorted(range(rep["tiles"]), key=lambda i: -rep["uses"][i])[:5]; print("  most used: " + ", ".join(f"{i}x{rep['uses'][i]}" for i in top if rep["uses"][i]))
    for w in rep["warnings"]: print("WARN " + w)
    if a.json: json.dump(rep, open(a.json, "w"), indent=1)
    if a.png: annotate(img, rep, a.margin, a.spacing).save(a.png)
    return 1 if (a.fail_on_unused and maps and rep["unused"]) or (a.fail_on_duplicates and rep["duplicates"]) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
