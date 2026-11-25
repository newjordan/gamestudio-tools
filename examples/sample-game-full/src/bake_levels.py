#!/usr/bin/env python3
"""Lay out the three levels on map-blank output: tile GIDs (with Tiled H, V
and diagonal flip flags), a hidden navstrip layer for enemy navigation, and an
object layer (spawn, enemies with patrol polylines, an animated gem tile
object, door tile objects, an exit rectangle).

The level *design* lives in LEVELS below; every pixel of art and every engine
file is produced by gst. Also writes <out>.gaps.json for jump-arc checks.
"""
import argparse, copy, json
from pathlib import Path

TILE, W, H = 16, 50, 12
FLIP_H, FLIP_V, FLIP_D = 0x80000000, 0x40000000, 0x20000000
# local tile id -> gid (firstgid 1)
GRASS, DIRT, BRICK, PLANK, EDGE, GEM, DOOR_T, DOOR_B, TORCH = 1, 2, 3, 4, 5, 6, 10, 11, 12
GRAVITY, JUMP_V, SPEED = 900.0, 320.0, 110.0

LEVELS = {
    1: dict(name="Meadow", floors=[(0, 14), (18, 49)], blocks=[(26, 27, 8)], planks=[(8, 11, 7)],
            enemies=[(34, "slime", 30, 41)], gem=21, door=46, torches=[5, 23, 43], ceiling=False),
    2: dict(name="Ruins", floors=[(0, 10), (14, 22), (25, 49)], blocks=[(30, 31, 8), (40, 41, 9)],
            planks=[(17, 20, 7)], enemies=[(18, "slime", 15, 21), (35, "slime_red", 32, 39)],
            gem=27, door=46, torches=[3, 28, 44], ceiling=False),
    3: dict(name="Cave", floors=[(0, 12), (16, 28), (32, 49)], blocks=[(20, 21, 8)], planks=[(36, 39, 7)],
            enemies=[(25, "slime", 22, 27), (41, "slime_red", 34, 44)], gem=33, door=46,
            torches=[6, 18, 42], ceiling=True),
}
FLOOR = 10  # grass row; dirt below


def layer(m, name):
    return next(l for l in m["layers"] if l["name"] == name)


def bake(blank, n):
    L = LEVELS[n]
    m = copy.deepcopy(blank)
    for l in m["layers"]:
        l["data"] = [0] * (W * H)
    g, p, nav = layer(m, "ground")["data"], layer(m, "platforms")["data"], layer(m, "navstrip")["data"]
    back = {"type": "tilelayer", "id": 10, "name": "back", "width": W, "height": H, "x": 0, "y": 0,
            "visible": True, "opacity": 1, "data": [0] * (W * H)}
    m["layers"].insert(0, back)
    b = back["data"]
    layer(m, "navstrip")["visible"] = False
    put = lambda arr, x, y, gid: arr.__setitem__(y * W + x, gid)
    for x0, x1 in L["floors"]:
        for x in range(x0, x1 + 1):
            put(g, x, FLOOR, GRASS)
            put(g, x, FLOOR + 1, DIRT)
        if x0 > 0:
            put(g, x0, FLOOR, EDGE)                  # rounded left lip
        if x1 < W - 1:
            put(g, x1, FLOOR, EDGE | FLIP_H)         # mirrored right lip
    for x0, x1, top in L["blocks"]:
        for x in range(x0, x1 + 1):
            for y in range(top, FLOOR):
                put(g, x, y, BRICK)
        # diagonal-flipped edge as moss on the block's left face (transpose + H)
        for y in range(top, FLOOR):
            put(b, x0 - 1, y, EDGE | FLIP_D | FLIP_H)
    for x0, x1, row in L["planks"]:
        for x in range(x0, x1 + 1):
            put(p, x, row, PLANK)
    if L["ceiling"]:
        for x in range(W):
            put(g, x, 0, BRICK)
            if x % 5 == 2:
                put(b, x, 1, EDGE | FLIP_V)          # hanging moss, flipped vertically
    for x in L["torches"]:
        put(b, x, FLOOR - 2, TORCH)
    # navstrip: the empty cell above every solid ground cell
    for x in range(W):
        for y in range(1, H):
            if g[y * W + x] and not g[(y - 1) * W + x]:
                put(nav, x, y - 1, DIRT)
    objs, oid = [], 1

    def obj(**kw):
        nonlocal oid
        kw.setdefault("rotation", 0); kw.setdefault("visible", True)
        kw.setdefault("width", 0); kw.setdefault("height", 0)
        kw["id"] = oid; oid += 1
        objs.append(kw)
        return kw
    ground_y = FLOOR * TILE
    obj(name="spawn", type="spawn", x=2 * TILE + 8, y=ground_y, point=True)
    for i, (ex, kind, a, z) in enumerate(L["enemies"], start=1):
        pl = obj(name=f"patrol_{i}", type="patrol", x=a * TILE + 8, y=ground_y - 8,
                 polyline=[{"x": 0, "y": 0}, {"x": (z - a) * TILE, "y": 0}])
        obj(name=f"enemy_{i}", type="enemy", x=ex * TILE + 8, y=ground_y, point=True,
            properties=[{"name": "kind", "type": "string", "value": kind},
                        {"name": "patrol", "type": "string", "value": pl["name"]}])
    obj(name="gem", type="gem", gid=GEM, x=L["gem"] * TILE, y=ground_y - 2, width=16, height=16)
    obj(name="door_top", type="door", gid=DOOR_T, x=L["door"] * TILE, y=ground_y - 16, width=16, height=16)
    obj(name="door_bottom", type="door", gid=DOOR_B, x=L["door"] * TILE, y=ground_y, width=16, height=16)
    obj(name="exit", type="exit", x=L["door"] * TILE, y=ground_y - 32, width=16, height=32)
    m["layers"].append({"type": "objectgroup", "id": 20, "name": "objects", "visible": True, "opacity": 1,
                        "x": 0, "y": 0, "draworder": "topdown", "objects": objs})
    m["nextobjectid"] = oid
    m["nextlayerid"] = 21
    m["properties"] = [{"name": "title", "type": "string", "value": L["name"]},
                       {"name": "level", "type": "int", "value": n}]
    ts = m["tilesets"][0]
    ts["tiles"] = [{"id": GEM - 1, "animation": [{"tileid": GEM - 1 + k, "duration": 120} for k in range(4)]}]
    gaps = []
    floors = L["floors"]
    for (a0, a1), (b0, b1) in zip(floors, floors[1:]):
        gaps.append({"takeoff": [(a1 + 1) * TILE - 2, ground_y - 12], "land_min": b0 * TILE,
                     "land_max": (b0 + 6) * TILE, "floor_y": ground_y})
    return m, gaps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("blank")
    ap.add_argument("--level", type=int, required=True, choices=sorted(LEVELS))
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    blank = json.loads(Path(a.blank).read_text())
    m, gaps = bake(blank, a.level)
    Path(a.out).write_text(json.dumps(m, indent=1))
    Path(a.out).with_suffix(".gaps.json").write_text(json.dumps(
        {"gravity": GRAVITY, "jump_v": JUMP_V, "speed": SPEED, "gaps": gaps}, indent=1))
    print(f"level {a.level} ({LEVELS[a.level]['name']}) -> {a.out}, {len(gaps)} gap(s)")


if __name__ == "__main__":
    main()
