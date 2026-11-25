#!/usr/bin/env python3
"""tilemap-convert: move level data between Tiled JSON, CSV and ASCII, and get tile statistics.

  to-csv   map.json -o prefix      one CSV per tile layer (prefix_<layer>.csv); flip flags stripped
  from-csv a.csv [b.csv] -o map.json --tile 16x16   build a Tiled-style map (one layer per CSV)
  to-ascii map.json --legend "1:.,2:#" [--layer NAME]   print/save a text map
  from-ascii map.txt -o map.json --legend ".:1,#:2" --tile 16x16
  stats    map.json                tile-id histogram per layer + flipped-tile count
Tiled stores flip/rotation flags in the top 3 bits of each GID (Tiled's documented format); we mask
them for CSV/ASCII and report how many were flipped so nothing is lost silently.
"""
import argparse, os, csv, json, sys
from collections import Counter

FLIPS = 0xE0000000
GID_MASK = 0x1FFFFFFF


def tile_layers(m):
    return [l for l in m["layers"] if l["type"] == "tilelayer"]


def layer_grid(l):
    w, h = l["width"], l["height"]
    d = l["data"]
    return [[d[y * w + x] & GID_MASK for x in range(w)] for y in range(h)]


def make_map(grids, tw, th, names=None):
    h, w = len(grids[0]), len(grids[0][0])
    return {"width": w, "height": h, "tilewidth": tw, "tileheight": th, "orientation": "orthogonal", "type": "map",
            "infinite": False, "renderorder": "right-down",
            "layers": [{"name": (names[i] if names else f"layer{i + 1}"), "type": "tilelayer", "width": w, "height": h,
                        "x": 0, "y": 0, "opacity": 1, "visible": True, "data": [v for row in g for v in row]}
                       for i, g in enumerate(grids)]}


def parse_legend(s, reverse=False):
    pairs = [p.split(":", 1) for p in s.split(",") if p]
    return {(b if reverse else a): (a if reverse else b) for a, b in pairs}


def stats(m):
    out = {}
    for l in tile_layers(m):
        c = Counter(v & GID_MASK for v in l["data"])
        out[l["name"]] = {"tiles": dict(sorted(c.items())), "empty": c.get(0, 0),
                          "flipped": sum(1 for v in l["data"] if v & FLIPS)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert tile maps between Tiled JSON, CSV and ASCII.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("to-csv"); s.add_argument("map"); s.add_argument("-o", "--out", required=True)
    s = sub.add_parser("from-csv"); s.add_argument("csvs", nargs="+"); s.add_argument("-o", "--out", required=True); s.add_argument("--tile", default="16x16")
    s = sub.add_parser("to-ascii"); s.add_argument("map"); s.add_argument("--legend", required=True); s.add_argument("--layer"); s.add_argument("-o", "--out")
    s = sub.add_parser("from-ascii"); s.add_argument("txt"); s.add_argument("-o", "--out", required=True); s.add_argument("--legend", required=True); s.add_argument("--tile", default="16x16")
    s = sub.add_parser("stats"); s.add_argument("map")
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
    _src_keys = ('map', 'txt', 'csvs')
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

    if a.cmd == "to-csv":
        m = json.load(open(a.map))
        for l in tile_layers(m):
            p = f"{a.out}_{l['name']}.csv"
            csv.writer(open(p, "w", newline="")).writerows(layer_grid(l))
            print(f"wrote {p}")
        fl = sum(v["flipped"] for v in stats(m).values())
        if fl:
            print(f"note: {fl} flipped/rotated tile(s) lost their flip flags in CSV", file=sys.stderr)
    elif a.cmd == "from-csv":
        grids = [[[int(c) for c in row] for row in csv.reader(open(p)) if row] for p in a.csvs]
        tw, th = (int(v) for v in a.tile.split("x"))
        json.dump(make_map(grids, tw, th, [os.path.splitext(os.path.basename(p))[0] for p in a.csvs]), open(a.out, "w"), indent=1)
        print(f"wrote {a.out} ({len(grids)} layer(s))")
    elif a.cmd == "to-ascii":
        m = json.load(open(a.map)); leg = parse_legend(a.legend)
        ls = tile_layers(m)
        l = next(x for x in ls if x["name"] == a.layer) if a.layer else ls[0]
        txt = "\n".join("".join(leg.get(str(v), "?") for v in row) for row in layer_grid(l)) + "\n"
        (open(a.out, "w").write(txt) if a.out else print(txt, end=""))
    elif a.cmd == "from-ascii":
        leg = parse_legend(a.legend)
        rows = [l.rstrip("\n") for l in open(a.txt) if l.strip()]
        grid = [[int(leg[ch]) for ch in r] for r in rows]
        tw, th = (int(v) for v in a.tile.split("x"))
        json.dump(make_map([grid], tw, th, ["ascii"]), open(a.out, "w"), indent=1)
        print(f"wrote {a.out}")
    else:
        for name, st in stats(json.load(open(a.map))).items():
            print(f"{name}: empty {st['empty']}, flipped {st['flipped']}, tiles {st['tiles']}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
