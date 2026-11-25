#!/usr/bin/env python3
"""map-auto-layer: build a decoration tile layer from a rule table over a Tiled ground
layer. Each rule matches a centre GID (optional) and a 4- or 8-neighbour pattern; the
first matching rule wins. Neighbours can be tested as solid (non-zero GID, default) or as
exact unmasked GIDs. Encoded source data is decoded. Writes a new map; the input is never
overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF

DIRS = {
    "n": (0, -1), "ne": (1, -1), "e": (1, 0), "se": (1, 1),
    "s": (0, 1), "sw": (-1, 1), "w": (-1, 0), "nw": (-1, -1),
}
DIR_KEYS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")


def find_layer(layers, name):
    for l in layers or []:
        if l.get("type") == "group":
            hit = find_layer(l.get("layers") or [], name)
            if hit is not None:
                return hit
        elif l.get("name") == name:
            return l
    return None


def grid_of(layer):
    if layer.get("type") != "tilelayer":
        raise SystemExit(f"layer {layer.get('name')!r} is not a tile layer")
    if layer.get("infinite") or "chunks" in layer:
        raise SystemExit("infinite maps are refused; run tmx-infinite-to-finite first")
    w, h = int(layer["width"]), int(layer["height"])
    data = list(layer.get("data") or [])
    if len(data) != w * h:
        raise SystemExit(f"layer {layer.get('name')!r} data length {len(data)} != {w}x{h}")
    return w, h, data


def cell(data, w, h, x, y):
    if x < 0 or y < 0 or x >= w or y >= h:
        return 0
    return data[y * w + x] & MASK


def as_list(val):
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return [int(x) for x in val]
    return [int(val)]


def neighbour_ok(rule, key, actual, match):
    if key not in rule:
        return True
    want = rule[key]
    if match == "solid":
        flag = 1 if actual else 0
        if isinstance(want, bool):
            return flag == (1 if want else 0)
        return flag == int(want)
    # exact gid(s)
    allowed = as_list(want)
    return actual in allowed


def rule_matches(rule, cx, neighbours, match):
    want_c = as_list(rule.get("center")) if "center" in rule else None
    if want_c is not None and cx not in want_c:
        return False
    if rule.get("center_empty") and cx != 0:
        return False
    for key in DIR_KEYS:
        if not neighbour_ok(rule, key, neighbours[key], match):
            return False
    return True


def apply_rules(data, w, h, rules, match, default=0):
    out = [default] * (w * h)
    placed = 0
    for y in range(h):
        for x in range(w):
            cx = cell(data, w, h, x, y)
            neigh = {k: cell(data, w, h, x + dx, y + dy) for k, (dx, dy) in DIRS.items()}
            if match == "solid":
                # solid tests use 0/1 already inside neighbour_ok
                pass
            for rule in rules:
                if rule_matches(rule, cx, neigh, match):
                    gid = int(rule["gid"])
                    out[y * w + x] = gid
                    if gid:
                        placed += 1
                    break
    return out, placed


def load_rules(path):
    raw = json.load(open(path, encoding="utf-8"))
    if isinstance(raw, list):
        raw = {"rules": raw}
    rules = raw.get("rules")
    if not isinstance(rules, list) or not rules:
        raise SystemExit(f"{path}: expected a 'rules' array")
    for i, r in enumerate(rules):
        if "gid" not in r:
            raise SystemExit(f"{path}: rule {i} is missing 'gid'")
    return raw


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a decoration tile layer from a neighbour-rule table.")
    ap.add_argument("map")
    ap.add_argument("--rules", required=True, help="JSON rule table")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--layer", help="source tile layer (default: rules.source, else the first tile layer)")
    ap.add_argument("--name", help="name of the new layer (default: rules.name or 'auto')")
    ap.add_argument("--match", choices=("solid", "gid"), help="override rules.match (default: solid)")
    ap.add_argument("--default", type=int, help="GID for unmatched cells (default: 0)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    table = load_rules(a.rules)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    src_name = a.layer or table.get("source")
    layers = m.get("layers") or []
    if src_name:
        src = find_layer(layers, src_name)
        if src is None:
            raise SystemExit(f"layer not found: {src_name}")
    else:
        src = next((l for l in map_diff.flat_layers(layers) if l.get("type") == "tilelayer" or "data" in l), None)
        # flat_layers may not set type; fall back
        if src is None:
            def first_tile(ls):
                for l in ls or []:
                    if l.get("type") == "group":
                        hit = first_tile(l.get("layers") or [])
                        if hit is not None:
                            return hit
                    elif l.get("type") == "tilelayer":
                        return l
                return None
            src = first_tile(layers)
        if src is None:
            raise SystemExit("no tile layer in map")
        src_name = src.get("name") or ""
    w, h, data = grid_of(src)
    match = a.match or table.get("match") or "solid"
    default = a.default if a.default is not None else int(table.get("default") or 0)
    grid, placed = apply_rules(data, w, h, table["rules"], match, default)
    name = a.name or table.get("name") or "auto"
    new_layer = {
        "type": "tilelayer", "name": name, "width": w, "height": h,
        "x": src.get("x", 0), "y": src.get("y", 0),
        "opacity": 1, "visible": True, "data": grid,
    }
    # insert after the source layer at the same depth when it is a top-level sibling
    inserted = False
    for i, l in enumerate(list(m.get("layers") or [])):
        if l is src or l.get("name") == src.get("name"):
            m["layers"].insert(i + 1, new_layer)
            inserted = True
            break
    if not inserted:
        m.setdefault("layers", []).append(new_layer)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"source": src.get("name"), "name": name, "placed": placed, "cells": w * h, "out": a.out}
    print(f"{placed} tile(s) on {name!r} ({w}x{h}) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
