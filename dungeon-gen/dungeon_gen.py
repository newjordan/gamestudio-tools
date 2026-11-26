#!/usr/bin/env python3
"""dungeon-gen: seeded roguelike layouts (BSP rooms+corridors or cellular-automata caves).

Exports ASCII preview, PNG, and a Tiled-compatible JSON map (tile ids: 1 floor, 2 wall) so it drops
straight into Tiled, LDtk import, or a Godot TileMap importer. The JSON embeds a two-tile tileset
(<out>_tiles.png: floor, wall; the wall tile carries a solid=true property) and, in BSP mode, a "rooms"
object layer with one rectangle per room (index, centre and size properties).
"""
import argparse, json, random
from PIL import Image
import os, sys

WALL, FLOOR = 1, 0


def bsp(w, h, seed=None, min_leaf=8, max_depth=5):
    rnd = random.Random(seed)
    g = [[WALL] * w for _ in range(h)]
    rooms = []

    def split(x, y, ww, hh, depth):
        if depth >= max_depth or (ww < min_leaf * 2 and hh < min_leaf * 2):
            rw = rnd.randint(max(3, ww // 2), max(3, ww - 2))
            rh = rnd.randint(max(3, hh // 2), max(3, hh - 2))
            rw, rh = min(rw, ww - 2), min(rh, hh - 2)
            if rw < 2 or rh < 2:
                return None
            rx = x + rnd.randint(1, ww - rw - 1)
            ry = y + rnd.randint(1, hh - rh - 1)
            for yy in range(ry, ry + rh):
                for xx in range(rx, rx + rw):
                    g[yy][xx] = FLOOR
            rooms.append((rx, ry, rw, rh))
            return (rx + rw // 2, ry + rh // 2)
        horiz = hh > ww if abs(hh - ww) > 4 else rnd.random() < 0.5
        if horiz and hh >= min_leaf * 2:
            cut = rnd.randint(min_leaf, hh - min_leaf)
            a = split(x, y, ww, cut, depth + 1)
            b = split(x, y + cut, ww, hh - cut, depth + 1)
        elif ww >= min_leaf * 2:
            cut = rnd.randint(min_leaf, ww - min_leaf)
            a = split(x, y, cut, hh, depth + 1)
            b = split(x + cut, y, ww - cut, hh, depth + 1)
        else:
            return split(x, y, ww, hh, max_depth)
        if a and b:
            carve(a, b)
        return a or b

    def carve(a, b):
        (x1, y1), (x2, y2) = a, b
        if rnd.random() < 0.5:
            for xx in range(min(x1, x2), max(x1, x2) + 1):
                g[y1][xx] = FLOOR
            for yy in range(min(y1, y2), max(y1, y2) + 1):
                g[yy][x2] = FLOOR
        else:
            for yy in range(min(y1, y2), max(y1, y2) + 1):
                g[yy][x1] = FLOOR
            for xx in range(min(x1, x2), max(x1, x2) + 1):
                g[y2][xx] = FLOOR

    split(0, 0, w, h, 0)
    return g, rooms


def caves(w, h, seed=None, fill=0.5, steps=4):
    rnd = random.Random(seed)
    g = [[WALL if (x in (0, w - 1) or y in (0, h - 1) or rnd.random() < fill) else FLOOR for x in range(w)] for y in range(h)]
    for _ in range(steps):
        n = [[WALL] * w for _ in range(h)]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                walls = sum(g[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
                n[y][x] = WALL if walls > 4 else FLOOR if walls < 4 else g[y][x]
        g = n
    return keep_largest(g), []


def regions(g):
    h, w = len(g), len(g[0])
    seen, out = set(), []
    for y in range(h):
        for x in range(w):
            if g[y][x] == FLOOR and (x, y) not in seen:
                comp, st = [], [(x, y)]
                seen.add((x, y))
                while st:
                    cx, cy = st.pop()
                    comp.append((cx, cy))
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < w and 0 <= ny < h and g[ny][nx] == FLOOR and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            st.append((nx, ny))
                out.append(comp)
    return out


def keep_largest(g):
    rs = regions(g)
    if not rs:
        return g
    big = set(max(rs, key=len))
    return [[FLOOR if (x, y) in big else WALL for x in range(len(g[0]))] for y in range(len(g))]


def to_ascii(g):
    return "\n".join("".join("#" if c == WALL else "." for c in row) for row in g)


FLOOR_RGB, WALL_RGB = (200, 196, 180), (52, 48, 64)


def tiles_image(tile=16):
    im = Image.new("RGBA", (tile * 2, tile), FLOOR_RGB + (255,))
    im.paste(WALL_RGB + (255,), (tile, 0, tile * 2, tile))
    return im


def to_tiled(g, tile=16, rooms=(), image="dungeon_tiles.png"):
    h, w = len(g), len(g[0])
    layers = [{"id": 1, "name": "dungeon", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
               "opacity": 1, "visible": True, "data": [2 if c == WALL else 1 for row in g for c in row]}]
    objs = []
    for i, (rx, ry, rw, rh) in enumerate(rooms):
        objs.append({"id": i + 1, "name": f"room{i}", "type": "room", "x": rx * tile, "y": ry * tile,
                     "width": rw * tile, "height": rh * tile, "rotation": 0, "visible": True,
                     "properties": [{"name": "index", "type": "int", "value": i},
                                    {"name": "cx", "type": "int", "value": rx + rw // 2},
                                    {"name": "cy", "type": "int", "value": ry + rh // 2},
                                    {"name": "w", "type": "int", "value": rw},
                                    {"name": "h", "type": "int", "value": rh}]})
    if rooms:
        layers.append({"id": 2, "name": "rooms", "type": "objectgroup", "x": 0, "y": 0, "opacity": 1,
                       "visible": True, "draworder": "topdown", "objects": objs})
    ts = {"firstgid": 1, "name": "dungeon", "image": image, "imagewidth": tile * 2, "imageheight": tile,
          "tilewidth": tile, "tileheight": tile, "tilecount": 2, "columns": 2, "margin": 0, "spacing": 0,
          "tiles": [{"id": 0, "type": "floor"},
                    {"id": 1, "type": "wall", "properties": [{"name": "solid", "type": "bool", "value": True}]}]}
    return {"width": w, "height": h, "tilewidth": tile, "tileheight": tile, "orientation": "orthogonal",
            "type": "map", "version": "1.10", "tiledversion": "1.10.2", "infinite": False,
            "renderorder": "right-down", "nextlayerid": len(layers) + 1, "nextobjectid": len(objs) + 1,
            "tilesets": [ts], "layers": layers}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate dungeon / cave layouts.")
    ap.add_argument("--mode", choices=["bsp", "caves"], default="bsp")
    ap.add_argument("--size", default="64x40")
    ap.add_argument("--seed", type=int)
    ap.add_argument("-o", "--out", default="dungeon", help="basename; writes .txt .png .json")
    ap.add_argument("--scale", type=int, default=8)
    ap.add_argument("--tile", type=int, default=16, help="tile size in pixels for the JSON map and its tileset image")
    a = ap.parse_args(argv)
    w, h = (int(v) for v in a.size.lower().split("x"))
    g, rooms = bsp(w, h, a.seed) if a.mode == "bsp" else caves(w, h, a.seed)
    open(a.out + ".txt", "w").write(to_ascii(g) + "\n")
    ap_tiles = a.out + "_tiles.png"
    tiles_image(a.tile).save(ap_tiles)
    json.dump(to_tiled(g, a.tile, rooms, os.path.basename(ap_tiles)), open(a.out + ".json", "w"))
    im = Image.new("L", (w, h))
    im.putdata([30 if c == WALL else 220 for row in g for c in row])
    im.resize((w * a.scale, h * a.scale), Image.Resampling.NEAREST).save(a.out + ".png")
    print(f"{a.mode} {w}x{h} seed={a.seed}: {len(rooms)} rooms, {len(regions(g))} connected region(s) -> {a.out}.txt/.png/.json (+ {os.path.basename(a.out)}_tiles.png)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
