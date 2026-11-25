#!/usr/bin/env python3
"""map-layer-merge: flatten named tile layers into one layer. Later layers overwrite earlier
non-empty cells; flip flags on the GID are kept. Object / group / unmentioned tile layers pass
through. Encoded (base64 zlib/gzip/csv) data is decoded to a plain array in the output. Writes a
new map; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def tile_layers(layers):
    for l in layers or []:
        if l.get("type") == "group":
            yield from tile_layers(l.get("layers") or [])
        elif l.get("type") == "tilelayer":
            yield l


def merge_grids(layers, w, h):
    out = [0] * (w * h)
    overwrites = 0
    filled = 0
    for l in layers:
        data = l.get("data") or []
        if len(data) != w * h:
            raise SystemExit(f"layer {l.get('name')!r} data length {len(data)} != {w}x{h}")
        for i, g in enumerate(data):
            if g:
                if out[i]:
                    overwrites += 1
                else:
                    filled += 1
                out[i] = int(g)
    return out, filled, overwrites


def main(argv=None):
    ap = argparse.ArgumentParser(description="Flatten named tile layers into one layer.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--layers", help="comma-separated tile layer names (default: all tile layers, in order)")
    ap.add_argument("--name", help="name of the merged layer (default: first source layer, or 'merged')")
    ap.add_argument("--drop-sources", action="store_true", help="remove the source tile layers after merging")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    if m.get("infinite"):
        sys.exit("infinite maps are not supported; convert to a finite map first")
    w, h = m["width"], m["height"]
    all_tl = list(tile_layers(m.get("layers") or []))
    names = [l["name"] for l in all_tl]
    if a.layers:
        want = [n.strip() for n in a.layers.split(",") if n.strip()]
        missing = [n for n in want if n not in names]
        if missing:
            sys.exit("unknown tile layer(s): " + ", ".join(missing) + " (have: " + ", ".join(names) + ")")
        sources = [l for l in all_tl if l["name"] in want]
        sources.sort(key=lambda l: want.index(l["name"]))
    else:
        want = names
        sources = all_tl
    if not sources:
        sys.exit("no tile layers to merge")
    grid, filled, overwrites = merge_grids(sources, w, h)
    merged_name = a.name or sources[0]["name"]
    merged = {"type": "tilelayer", "name": merged_name, "width": w, "height": h,
              "visible": True, "data": grid}
    src_names = {l["name"] for l in sources}
    first_i = next(i for i, l in enumerate(m["layers"]) if l.get("type") == "tilelayer" and l["name"] in src_names)

    def keep(layers):
        out = []
        for l in layers:
            if l.get("type") == "group":
                kids = keep(l.get("layers") or [])
                if kids or not a.drop_sources:
                    g = dict(l); g["layers"] = kids; out.append(g)
            elif l.get("type") == "tilelayer" and l["name"] in src_names:
                if not a.drop_sources:
                    out.append(l)
            else:
                out.append(l)
        return out

    if a.drop_sources:
        layers = keep(m["layers"])
        layers.insert(min(first_i, len(layers)), merged)
        m["layers"] = layers
    else:
        # insert merged just before the first source at top level when possible
        m["layers"] = list(m["layers"])
        m["layers"].insert(first_i, merged)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"sources": [l["name"] for l in sources], "name": merged_name,
           "cells_filled": filled, "cells_overwritten": overwrites, "out": a.out}
    print(f"merged {len(sources)} layer(s) -> {merged_name} ({filled} filled, {overwrites} overwritten) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
