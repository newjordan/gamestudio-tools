#!/usr/bin/env python3
"""Fill a map-blank Tiled JSON with a tiny top-down room: floor, walls, spawn, coin."""
from __future__ import annotations

import argparse, json, os, sys
from PIL import Image


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bake a 20x10 top-down room into a blank Tiled map.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tileset", help="tileset PNG; imagewidth/imageheight are updated from it")
    a = ap.parse_args(argv)
    m = json.load(open(a.input, encoding="utf-8"))
    w, h = m["width"], m["height"]
    if w < 8 or h < 6:
        raise SystemExit(f"map is too small for the room ({w}x{h})")
    ground = walls = None
    for l in m["layers"]:
        if l.get("name") == "ground" and l.get("type") == "tilelayer":
            ground = l
        elif l.get("name") == "walls" and l.get("type") == "tilelayer":
            walls = l
    if ground is None or walls is None:
        raise SystemExit("expected ground and walls tile layers")
    # GID 1 = floor, GID 2 = wall
    g = [1] * (w * h)
    s = [0] * (w * h)

    def wall(tx, ty):
        if 0 <= tx < w and 0 <= ty < h:
            s[ty * w + tx] = 2

    for x in range(w):
        wall(x, 0); wall(x, h - 1)
    for y in range(h):
        wall(0, y); wall(w - 1, y)
    # 2x2 interior block, leaving a corridor around it
    for tx, ty in ((4, 2), (5, 2), (4, 3), (5, 3)):
        wall(tx, ty)

    ground["data"] = g
    walls["data"] = s

    tw, th = m["tilewidth"], m["tileheight"]
    spawn = {"id": 1, "name": "spawn", "type": "spawn",
             "x": 2 * tw, "y": (h - 3) * th, "width": tw, "height": th}
    coin = {"id": 2, "name": "coin", "type": "coin",
            "x": (w - 5) * tw, "y": 2 * th, "width": tw, "height": th}
    objs = {
        "type": "objectgroup", "id": 3, "name": "objects",
        "visible": True, "opacity": 1, "x": 0, "y": 0,
        "objects": [spawn, coin],
    }
    # replace existing objects layer if present
    m["layers"] = [l for l in m["layers"] if l.get("name") != "objects"]
    m["layers"].append(objs)
    m["nextlayerid"] = max(m.get("nextlayerid") or 1, 4)
    m["nextobjectid"] = 3

    if a.tileset and os.path.isfile(a.tileset):
        im = Image.open(a.tileset)
        for ts in m.get("tilesets") or []:
            ts["image"] = os.path.basename(a.tileset)
            ts["imagewidth"], ts["imageheight"] = im.size

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    print("baked room %dx%d spawn=(%s,%s) coin=(%s,%s) -> %s" % (
        w, h, spawn["x"], spawn["y"], coin["x"], coin["y"], a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
