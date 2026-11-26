#!/usr/bin/env python3
"""Finish one Ember Crypt map: swap in the game tilesets, drop the raw
dungeon-gen layer, and populate the rooms with seeded objects.

Input is the map after two map-auto-layer passes (layers: dungeon, floor,
walls, and for floors a dungeon-gen "rooms" object layer). The tile art lives
in two tilesets: the tileset-gen blob sheet (GIDs 1-48, walls) and the props
sheet (GID 49 floor, 50 shadowed floor, 51 stairs, 52 rune).

Floors: spawn in the first room, stairs (a tile object) in the room farthest
from it by walking distance, the key in the next farthest, one enemy in every
other room (kinds and positions from the seed), coins and hearts. Boss arena:
spawn at the bottom, the boss at the top, a portal point in the middle.
"""
import argparse, json, random
from collections import deque
from pathlib import Path

TILE = 16
STAIRS_GID = 51
KINDS = {1: ["bat", "wizard"], 2: ["bat_red", "warlock", "bat"]}
MAX_ENEMIES = {1: 4, 2: 5}


def layer(m, name):
    return next((l for l in m["layers"] if l.get("name") == name), None)


def bfs(grid, w, h, start):
    dist = {start: 0}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny * w + nx] == 1 and (nx, ny) not in dist:
                dist[(nx, ny)] = dist[(x, y)] + 1
                q.append((nx, ny))
    return dist


class Objects:
    def __init__(self):
        self.items, self.next = [], 1

    def point(self, name, typ, cx, cy, **props):
        o = {"id": self.next, "name": name, "type": typ, "point": True, "rotation": 0, "visible": True,
             "x": cx * TILE + TILE // 2, "y": cy * TILE + TILE // 2, "width": 0, "height": 0}
        if props:
            o["properties"] = [{"name": k, "type": "int" if isinstance(v, int) else "string", "value": v}
                               for k, v in props.items()]
        self.items.append(o)
        self.next += 1

    def tile(self, name, typ, gid, cx, cy):
        # Tiled tile objects are anchored at their bottom-left corner
        self.items.append({"id": self.next, "name": name, "type": typ, "gid": gid, "rotation": 0, "visible": True,
                           "x": cx * TILE, "y": (cy + 1) * TILE, "width": TILE, "height": TILE})
        self.next += 1


def free_cell(rnd, room, grid, w, used):
    rx, ry, rw, rh = room
    cells = [(x, y) for y in range(ry + 1, ry + rh - 1) for x in range(rx + 1, rx + rw - 1)
             if grid[y * w + x] == 1 and (x, y) not in used]
    if not cells:
        cells = [(x, y) for y in range(ry, ry + rh) for x in range(rx, rx + rw)
                 if grid[y * w + x] == 1 and (x, y) not in used]
    c = rnd.choice(cells)
    used.add(c)
    return c


def populate_floor(m, raw, w, h, seed, floor):
    rnd = random.Random(seed * 100 + floor)
    rooms = [(o["x"] // TILE, o["y"] // TILE, o["width"] // TILE, o["height"] // TILE)
             for o in layer(m, "rooms")["objects"]]
    centre = lambda r: (r[0] + r[2] // 2, r[1] + r[3] // 2)
    spawn = centre(rooms[0])
    dist = bfs(raw, w, h, spawn)
    order = sorted(range(1, len(rooms)), key=lambda i: dist.get(centre(rooms[i]), -1), reverse=True)
    stairs_room, key_room = order[0], order[1]
    objs, used = Objects(), {spawn}
    objs.point("spawn", "spawn", *spawn)
    sx, sy = centre(rooms[stairs_room])
    used.add((sx, sy))
    objs.tile("stairs", "stairs", STAIRS_GID, sx, sy)
    objs.point("key", "key", *free_cell(rnd, rooms[key_room], raw, w, used))
    enemy_rooms = [i for i in range(1, len(rooms))][: MAX_ENEMIES[floor]]
    for n, i in enumerate(enemy_rooms):
        kind = rnd.choice(KINDS[floor])
        objs.point(f"enemy{n}", "enemy", *free_cell(rnd, rooms[i], raw, w, used), kind=kind)
    for n in range(2):
        objs.point(f"coin{n}", "coin", *free_cell(rnd, rooms[rnd.randrange(len(rooms))], raw, w, used))
    if floor >= 2:
        objs.point("heart0", "heart", *free_cell(rnd, rooms[rnd.randrange(1, len(rooms))], raw, w, used))
    return objs


def populate_boss(w, h):
    objs = Objects()
    objs.point("spawn", "spawn", w // 2, h - 3)
    objs.point("boss", "enemy", w // 2, 3, kind="boss")
    objs.point("portal", "portal", w // 2, h // 2)
    objs.point("heart0", "heart", 2, h - 3)
    return objs


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--mode", choices=("floor", "boss"), required=True)
    ap.add_argument("--floor", type=int, default=1)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    m = json.load(open(a.map))
    w, h = m["width"], m["height"]
    raw = [g & 0x1FFFFFFF for g in layer(m, "dungeon")["data"]]
    objs = populate_floor(m, raw, w, h, a.seed, a.floor) if a.mode == "floor" else populate_boss(w, h)
    m["layers"] = [l for l in m["layers"] if l.get("name") not in ("dungeon", "rooms")]
    for i, l in enumerate(m["layers"]):
        l["id"] = i + 1
    m["layers"].append({"id": len(m["layers"]) + 1, "name": "objects", "type": "objectgroup", "x": 0, "y": 0,
                        "opacity": 1, "visible": True, "draworder": "topdown", "objects": objs.items})
    m["nextlayerid"] = len(m["layers"]) + 1
    m["nextobjectid"] = objs.next
    m["tilesets"] = [
        {"firstgid": 1, "name": "walls", "image": "../art/walls.png", "imagewidth": 128, "imageheight": 96,
         "tilewidth": TILE, "tileheight": TILE, "tilecount": 48, "columns": 8, "margin": 0, "spacing": 0},
        {"firstgid": 49, "name": "props", "image": "../art/props.png", "imagewidth": 64, "imageheight": 16,
         "tilewidth": TILE, "tileheight": TILE, "tilecount": 4, "columns": 4, "margin": 0, "spacing": 0},
    ]
    m.setdefault("properties", []).extend([
        {"name": "title", "type": "string", "value": a.name},
        {"name": "seed", "type": "int", "value": a.seed},
        {"name": "floor", "type": "int", "value": a.floor}])
    m.setdefault("version", "1.10"); m.setdefault("tiledversion", "1.10.2")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=1)
    kinds = {}
    for o in objs.items:
        kinds[o["type"]] = kinds.get(o["type"], 0) + 1
    print(f"{a.out}: {w}x{h}, objects {kinds}")


if __name__ == "__main__":
    main()
