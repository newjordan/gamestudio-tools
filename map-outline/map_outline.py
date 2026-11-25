#!/usr/bin/env python3
"""map-outline: find the 4-connected outline of solid cells on a finite
orthogonal Tiled JSON map (same walkability as map-reach). Writes an optional
JSON report, a PNG overlay, and/or a copy of the map with an `outline` tile
layer. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-reach"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_reach, map_diff  # noqa: E402

NB = ((-1, 0), (1, 0), (0, -1), (0, 1))


def parse_ids(s):
    if not s:
        return ()
    return tuple(int(x) for x in s.split(",") if x.strip())


def outline_mask(solid):
    """solid is True where blocked. Outline = solid cells 4-adjacent to a
    non-solid cell or to the map edge."""
    h, w = solid.shape
    out = np.zeros_like(solid, dtype=bool)
    for y in range(h):
        for x in range(w):
            if not solid[y, x]:
                continue
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                out[y, x] = True
                continue
            for dx, dy in NB:
                nx, ny = x + dx, y + dy
                if not solid[ny, nx]:
                    out[y, x] = True
                    break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Outline solid cells on a Tiled JSON map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", help="optional Tiled JSON with an outline tile layer")
    ap.add_argument("--json")
    ap.add_argument("--png")
    ap.add_argument("--solid-layer")
    ap.add_argument("--solid-ids")
    ap.add_argument("--ground-layer")
    ap.add_argument("--gid", type=int, default=1, help="GID used on the outline layer (default: 1)")
    ap.add_argument("--layer-name", default="outline")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    for dest in (a.out, a.json, a.png):
        if dest:
            safe_out.check(a.map, dest, a.in_place)
    if not (a.out or a.json or a.png):
        raise SystemExit("pass --out, --json and/or --png")

    m = map_diff.decode_map(json.load(open(a.map, encoding="utf-8")))
    walk = map_reach.walkable_grid(m, a.solid_layer, parse_ids(a.solid_ids), a.ground_layer)
    solid = ~np.asarray(walk, dtype=bool)
    mask = outline_mask(solid)
    cells = [[int(x), int(y)] for y, x in zip(*np.where(mask))]
    rec = {"width": int(solid.shape[1]), "height": int(solid.shape[0]),
           "outline_count": len(cells), "solid_count": int(solid.sum()),
           "cells": cells}

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    if a.png:
        h, w = solid.shape
        tw = max(4, int(m.get("tilewidth") or 8) // 2)
        im = Image.new("RGB", (w * tw, h * tw), (20, 20, 24))
        dr = ImageDraw.Draw(im)
        for y in range(h):
            for x in range(w):
                box = (x * tw, y * tw, (x + 1) * tw - 1, (y + 1) * tw - 1)
                if mask[y, x]:
                    dr.rectangle(box, fill=(220, 80, 60))
                elif solid[y, x]:
                    dr.rectangle(box, fill=(80, 50, 50))
                else:
                    dr.rectangle(box, fill=(40, 80, 50))
        os.makedirs(os.path.dirname(os.path.abspath(a.png)) or ".", exist_ok=True)
        im.save(a.png)
    if a.out:
        out = json.loads(json.dumps(m))
        data = [int(a.gid) if mask[y, x] else 0
                for y in range(mask.shape[0]) for x in range(mask.shape[1])]
        layer = {
            "type": "tilelayer", "name": a.layer_name,
            "width": int(mask.shape[1]), "height": int(mask.shape[0]),
            "visible": True, "opacity": 1, "x": 0, "y": 0, "data": data,
            "id": int(out.get("nextlayerid") or 1),
        }
        out.setdefault("layers", []).append(layer)
        out["nextlayerid"] = int(out.get("nextlayerid") or 1) + 1
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(out, open(a.out, "w"), indent=2)

    print("outline %d cell(s) of %d solid -> %s" % (
        rec["outline_count"], rec["solid_count"],
        a.out or a.json or a.png))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
