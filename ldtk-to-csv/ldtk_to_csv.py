#!/usr/bin/env python3
"""ldtk-to-csv: export LDtk (.ldtk) projects to plain files engines and the other tools in this kit read:
IntGrid layers -> CSV of values, tile / auto layers -> CSV of tile ids (tileset tile id + 1, 0 = empty),
entities -> one CSV per level (identifier, x, y, w, h, fields), and optionally a Tiled-style JSON map per level.
Reads the documented LDtk JSON layout (levels -> layerInstances; __type IntGrid/Tiles/AutoLayer/Entities,
__cWid/__cHei, __gridSize, intGridCsv, gridTiles/autoLayerTiles {px, src, f, t}, entityInstances).
Projects saved with "Save levels to separate files" keep layers in external level files; point --levels-dir at them.
"""
import argparse, csv, json, os
import os, sys


def level_layers(level, levels_dir=None, base=None):
    if level.get("layerInstances") is None and level.get("externalRelPath"):
        p = os.path.join(levels_dir or base or ".", os.path.basename(level["externalRelPath"]) if levels_dir else level["externalRelPath"])
        level = json.load(open(p))
    return level.get("layerInstances") or []


def layer_grid(l):
    w, h, gs = l["__cWid"], l["__cHei"], l["__gridSize"]
    if l["__type"] == "IntGrid":
        v = l["intGridCsv"]; return [[v[y * w + x] for x in range(w)] for y in range(h)]
    tiles = l.get("gridTiles") or l.get("autoLayerTiles") or []
    g = [[0] * w for _ in range(h)]
    for t in tiles:
        x, y = t["px"][0] // gs, t["px"][1] // gs
        if 0 <= x < w and 0 <= y < h: g[y][x] = t["t"] + 1
    return g


def entities(layers):
    rows = []
    for l in layers:
        if l["__type"] != "Entities": continue
        for e in l["entityInstances"]:
            rows.append({"layer": l["__identifier"], "identifier": e["__identifier"], "x": e["px"][0], "y": e["px"][1], "w": e.get("width", 0), "h": e.get("height", 0),
                         "fields": json.dumps({f["__identifier"]: f["__value"] for f in e.get("fieldInstances", [])}, ensure_ascii=False)})
    return rows


def to_tiled(level, layers):
    tl = [l for l in layers if l["__type"] != "Entities"]
    if not tl: return None
    gs = tl[0]["__gridSize"]; w, h = tl[0]["__cWid"], tl[0]["__cHei"]
    return {"type": "map", "orientation": "orthogonal", "width": w, "height": h, "tilewidth": gs, "tileheight": gs, "infinite": False, "renderorder": "right-down",
            "layers": [{"id": i + 1, "name": l["__identifier"], "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0, "opacity": 1, "visible": True,
                        "data": [v for row in layer_grid(l) for v in row]} for i, l in enumerate(tl)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="LDtk project to CSV / Tiled JSON.")
    ap.add_argument("ldtk"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("--levels-dir"); ap.add_argument("--tiled", action="store_true", help="also write <level>.json maps")
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
    _src_keys = ('ldtk',)
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

    proj = json.load(open(a.ldtk)); os.makedirs(a.outdir, exist_ok=True); n = 0
    for lv in proj["levels"]:
        layers = level_layers(lv, a.levels_dir, os.path.dirname(os.path.abspath(a.ldtk)))
        for l in layers:
            if l["__type"] == "Entities": continue
            with open(os.path.join(a.outdir, f"{lv['identifier']}_{l['__identifier']}.csv"), "w", newline="") as f: csv.writer(f).writerows(layer_grid(l)); n += 1
        ents = entities(layers)
        if ents:
            with open(os.path.join(a.outdir, f"{lv['identifier']}_entities.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(ents[0])); w.writeheader(); w.writerows(ents); n += 1
        if a.tiled and (m := to_tiled(lv, layers)): json.dump(m, open(os.path.join(a.outdir, f"{lv['identifier']}.json"), "w"), indent=1); n += 1
    print(f"{len(proj['levels'])} level(s), {n} file(s) -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
