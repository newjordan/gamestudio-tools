#!/usr/bin/env python3
"""map-layer-split: split a tile layer into one layer per tileset (GID ranges). Flip flags
are kept; cells whose unmasked GID falls in a tileset's [firstgid, firstgid+tilecount) go on
that tileset's layer, the rest on an optional leftover layer. Encoded data is decoded.
Writes a new map; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLAGS = 0xE0000000


def tile_layers(layers):
    for l in layers or []:
        if l.get("type") == "group":
            yield from tile_layers(l.get("layers") or [])
        elif l.get("type") == "tilelayer":
            yield l


def ranges(tilesets):
    out = []
    for ts in tilesets or []:
        fg = int(ts.get("firstgid") or 1)
        count = int(ts.get("tilecount") or 0)
        name = ts.get("name") or ts.get("source") or f"gid{fg}"
        if count <= 0:
            # open-ended until next firstgid
            out.append((fg, None, name, ts))
        else:
            out.append((fg, fg + count, name, ts))
    # resolve open ends
    starts = sorted(r[0] for r in out)
    resolved = []
    for fg, end, name, ts in out:
        if end is None:
            nxt = min((s for s in starts if s > fg), default=None)
            end = nxt if nxt is not None else (1 << 28)
        resolved.append((fg, end, name, ts))
    return resolved


def split_data(data, ranges_):
    layers = {name: [0] * len(data) for _, _, name, _ in ranges_}
    leftover = [0] * len(data)
    counts = {name: 0 for name in layers}
    n_left = 0
    for i, g in enumerate(data):
        if not g:
            continue
        gid = int(g) & MASK
        flags = int(g) & FLAGS
        placed = False
        for fg, end, name, _ts in ranges_:
            if fg <= gid < end:
                layers[name][i] = gid | flags
                counts[name] += 1
                placed = True
                break
        if not placed:
            leftover[i] = int(g)
            n_left += 1
    return layers, leftover, counts, n_left


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a tile layer into one layer per tileset.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--layer", help="tile layer to split (default: the first tile layer)")
    ap.add_argument("--prefix", default="", help="prepended to each output layer name")
    ap.add_argument("--leftover", default="unassigned", help="name for GIDs that match no tileset")
    ap.add_argument("--no-leftover", action="store_true", help="drop unassigned cells instead of a leftover layer")
    ap.add_argument("--drop-source", action="store_true", help="remove the source layer after splitting")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    if m.get("infinite"):
        sys.exit("infinite maps are not supported; convert to a finite map first")
    all_tl = list(tile_layers(m.get("layers") or []))
    if not all_tl:
        sys.exit("no tile layers")
    if a.layer:
        src = next((l for l in all_tl if l["name"] == a.layer), None)
        if src is None:
            sys.exit(f"tile layer {a.layer!r} not found (have: {', '.join(l['name'] for l in all_tl)})")
    else:
        src = all_tl[0]
    rng = ranges(m.get("tilesets") or [])
    if not rng:
        sys.exit("map has no tilesets to split by")
    grids, leftover, counts, n_left = split_data(src.get("data") or [], rng)
    w, h = src.get("width", m["width"]), src.get("height", m["height"])
    new_layers = []
    for fg, end, name, _ts in rng:
        new_layers.append({"type": "tilelayer", "name": a.prefix + name, "width": w, "height": h,
                           "visible": True, "data": grids[name]})
    if n_left and not a.no_leftover:
        new_layers.append({"type": "tilelayer", "name": a.prefix + a.leftover, "width": w, "height": h,
                           "visible": True, "data": leftover})
    # splice into top-level layers at the source index when possible
    layers = list(m.get("layers") or [])
    idx = next((i for i, l in enumerate(layers) if l is src or (l.get("type") == "tilelayer" and l.get("name") == src["name"])), 0)
    if a.drop_source:
        layers = [l for i, l in enumerate(layers) if not (l.get("type") == "tilelayer" and l.get("name") == src["name"])]
        if idx > len(layers):
            idx = len(layers)
    layers[idx:idx] = new_layers
    m["layers"] = layers
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"source": src["name"], "layers": {n: c for n, c in counts.items()},
           "unassigned": n_left, "out": a.out}
    print(f"split {src['name']} into {len(new_layers)} layer(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
