#!/usr/bin/env python3
"""map-fill: rectangle-fill or 4-connected flood-fill cells on a Tiled tile layer.
`--rect x,y,w,h` writes `--gid` into that rectangle (clipped to the layer). `--flood x,y`
replaces the connected region of the cell under (x,y) with `--gid`. `--only-gid` limits a
rect fill to cells that already have that unmasked GID. Encoded data is decoded. Writes a
new map; the input is never overwritten unless `--in-place`. Infinite maps are refused.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLAGS = 0xE0000000


def find_layer(layers, name):
    for l in layers or []:
        if l.get("type") == "group":
            hit = find_layer(l.get("layers") or [], name)
            if hit is not None:
                return hit
        elif l.get("name") == name or (name is None and l.get("type") == "tilelayer"):
            if l.get("type") == "tilelayer" or "data" in l:
                return l
    return None


def first_tile(layers):
    for l in layers or []:
        if l.get("type") == "group":
            hit = first_tile(l.get("layers") or [])
            if hit is not None:
                return hit
        elif l.get("type") == "tilelayer":
            return l
    return None


def grid_of(layer):
    if layer.get("infinite") or "chunks" in layer:
        raise SystemExit("infinite maps are refused; run tmx-infinite-to-finite first")
    w, h = int(layer["width"]), int(layer["height"])
    data = list(layer.get("data") or [])
    if len(data) != w * h:
        raise SystemExit(f"layer {layer.get('name')!r} data length {len(data)} != {w}x{h}")
    return w, h, data


def parse_xy(s, n, label):
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != n:
        raise SystemExit(f"{label} expects {n} comma-separated integers")
    try:
        return [int(p) for p in parts]
    except ValueError:
        raise SystemExit(f"{label} expects integers")


def flood(data, w, h, x, y, new_gid):
    if x < 0 or y < 0 or x >= w or y >= h:
        raise SystemExit(f"flood start {x},{y} is outside {w}x{h}")
    start = data[y * w + x]
    target = start & MASK
    flags = start & FLAGS
    # replace the unmasked region; keep each cell's own flags unless the cell is empty
    if target == (new_gid & MASK) and (start == new_gid or target == 0):
        return 0
    seen = 0
    stack = [(x, y)]
    vis = set()
    while stack:
        cx, cy = stack.pop()
        if (cx, cy) in vis or cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        vis.add((cx, cy))
        i = cy * w + cx
        if (data[i] & MASK) != target:
            continue
        data[i] = (new_gid & MASK) | (data[i] & FLAGS if (new_gid & MASK) else 0)
        seen += 1
        stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
    return seen


def rect_fill(data, w, h, x, y, rw, rh, new_gid, only_gid=None):
    n = 0
    for yy in range(y, y + rh):
        for xx in range(x, x + rw):
            if xx < 0 or yy < 0 or xx >= w or yy >= h:
                continue
            i = yy * w + xx
            if only_gid is not None and (data[i] & MASK) != only_gid:
                continue
            data[i] = new_gid & MASK if (new_gid & MASK) == 0 else ((new_gid & MASK) | (data[i] & FLAGS))
            # if caller passed flags on --gid, honour them
            if new_gid & FLAGS:
                data[i] = new_gid
            n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rectangle- or flood-fill a Tiled tile layer.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--layer", help="tile layer name (default: the first tile layer)")
    ap.add_argument("--gid", type=int, required=True, help="GID to write (0 clears)")
    ap.add_argument("--rect", help="x,y,w,h rectangle in tile cells")
    ap.add_argument("--flood", help="x,y 4-connected flood fill start")
    ap.add_argument("--only-gid", type=int, help="rect: only replace this unmasked GID")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    if bool(a.rect) == bool(a.flood):
        sys.exit("pass exactly one of --rect or --flood")
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    src = find_layer(m.get("layers") or [], a.layer) if a.layer else first_tile(m.get("layers") or [])
    if src is None:
        sys.exit("tile layer not found" if a.layer else "no tile layer in map")
    w, h, data = grid_of(src)
    if a.rect:
        x, y, rw, rh = parse_xy(a.rect, 4, "--rect")
        n = rect_fill(data, w, h, x, y, rw, rh, a.gid, a.only_gid)
        kind = "rect"
    else:
        x, y = parse_xy(a.flood, 2, "--flood")
        n = flood(data, w, h, x, y, a.gid)
        kind = "flood"
    src["data"] = data
    src.pop("encoding", None)
    src.pop("compression", None)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"layer": src.get("name"), "mode": kind, "cells": n, "gid": a.gid, "out": a.out}
    print(f"{kind} {n} cell(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
