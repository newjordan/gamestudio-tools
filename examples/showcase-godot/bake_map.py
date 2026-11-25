#!/usr/bin/env python3
"""Bake a dungeon-gen Tiled JSON into TileMapLayer cell data using a tileset-gen lookup."""
import argparse, json, sys

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def mask_for(grid, x, y, bits):
    h, w = len(grid), len(grid[0])
    m = 0
    for name, dx, dy in (
        ("N", 0, -1), ("NE", 1, -1), ("E", 1, 0), ("SE", 1, 1),
        ("S", 0, 1), ("SW", -1, 1), ("W", -1, 0), ("NW", -1, -1),
    ):
        xx, yy = x + dx, y + dy
        if 0 <= xx < w and 0 <= yy < h and grid[yy][xx]:
            m |= bits[name]
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake dungeon + tileset-gen lookup to cells.json")
    ap.add_argument("dungeon", help="dungeon-gen Tiled JSON (gid 1=floor, 2=wall)")
    ap.add_argument("tileset", help="tileset-gen meta JSON with lookup and bits")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--wall-id", type=int, default=0,
                    help="atlas tile index used for every wall cell (default 0)")
    a = ap.parse_args(argv)
    tiled = json.load(open(a.dungeon, encoding="utf-8"))
    meta = json.load(open(a.tileset, encoding="utf-8"))
    lookup = meta["lookup"]
    bits = meta["bits"]
    cols = int(meta.get("columns") or 8)
    w, h = tiled["width"], tiled["height"]
    data = tiled["layers"][0]["data"]
    floor = [[1 if data[y * w + x] == 1 else 0 for x in range(w)] for y in range(h)]
    wall = [[data[y * w + x] == 2 for x in range(w)] for y in range(h)]
    floor_fallback = lookup[bits["N"]]  # avoid the solid-wall graphic (index 0) on a floor
    tiles = []
    for y in range(h):
        for x in range(w):
            if wall[y][x]:
                idx = a.wall_id
            else:
                idx = lookup[mask_for(floor, x, y, bits)]
                if idx == 0:
                    idx = floor_fallback
            tiles.append({
                "x": x, "y": y, "id": idx,
                "atlas_x": idx % cols, "atlas_y": idx // cols,
                "wall": bool(wall[y][x]),
            })
    spawn = wall_dir = walk_dir = None
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if wall[y][x]:
                continue
            for dx, dy in DIRS:
                if not wall[y + dy][x + dx]:
                    continue
                spawn = {"x": x, "y": y}
                wall_dir = {"x": dx, "y": dy}
                for ox, oy in DIRS:
                    if not wall[y + oy][x + ox]:
                        walk_dir = {"x": ox, "y": oy}
                        break
                else:
                    walk_dir = {"x": 0, "y": 0}
                break
            if spawn:
                break
        if spawn:
            break
    if not spawn:
        sys.exit("no floor cell adjacent to a wall (cannot place the collision test)")
    out = {
        "tile": int(meta.get("tile") or tiled.get("tilewidth") or 16),
        "columns": cols, "width": w, "height": h,
        "tiles": tiles, "spawn": spawn, "wall_dir": wall_dir, "walk_dir": walk_dir,
    }
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"baked {w}x{h} cells, spawn={spawn} wall_dir={wall_dir} walk_dir={walk_dir} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
