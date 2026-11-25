#!/usr/bin/env python3
"""Place tiles on a blank Tiled map and write Godot spawn / gap / physics metadata.

Art stays kit-generated; this script only writes GIDs and JSON. Gap records are
what the build script feeds to jump-arc and what the Godot verify uses to know
where a scripted jump must land.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

TILE = 16
MAP_W, MAP_H = 32, 12
# Solid floors at tile-row 10 (and a dirt row under them at 11).
# Gaps are 3 tiles wide (48 px), inside the ~66 px same-height jump range
# at GRAVITY=800, JUMP_V=220, SPEED=120.
FLOOR_Y = 10
DIRT_Y = 11
# inclusive tile-x ranges
SOLID = [(0, 7), (11, 16), (20, 31)]
GAPS = [(8, 10), (17, 19)]
# one-way platform on a mid layer, above the second floor (out of the first jump apex)
ONE_WAY = [(13, 15, 7)]
# GIDs: firstgid 1 → grass=1, dirt=2, one-way=3
GID_GRASS, GID_DIRT, GID_ONEWAY = 1, 2, 3
GRAVITY, JUMP_V, SPEED = 800.0, 220.0, 120.0
# CharacterBody2D collision is 10x14, centered; feet sit on the floor pixel.
HALF_H = 7.0
SPAWN_TX, SPAWN_TY = 3, FLOOR_Y


def _blank_layer(name, w, h):
    return {
        "type": "tilelayer", "name": name, "width": w, "height": h,
        "x": 0, "y": 0, "visible": True, "opacity": 1, "data": [0] * (w * h),
        "id": 1 if name == "ground" else 2,
    }


def _index(x, y, w):
    return y * w + x


def _in_solid(tx):
    return any(a <= tx <= b for a, b in SOLID)


def build_map(src: dict) -> dict:
    w = int(src.get("width") or MAP_W)
    h = int(src.get("height") or MAP_H)
    if w != MAP_W or h != MAP_H:
        raise SystemExit(f"expected a {MAP_W}x{MAP_H} map, got {w}x{h}")
    layers = {l.get("name"): l for l in src.get("layers") or [] if l.get("type") == "tilelayer"}
    ground = layers.get("ground") or _blank_layer("ground", w, h)
    plats = layers.get("platforms") or _blank_layer("platforms", w, h)
    ground["data"] = [0] * (w * h)
    plats["data"] = [0] * (w * h)
    for tx in range(w):
        if _in_solid(tx):
            ground["data"][_index(tx, FLOOR_Y, w)] = GID_GRASS
            if DIRT_Y < h:
                ground["data"][_index(tx, DIRT_Y, w)] = GID_DIRT
    for x0, x1, ty in ONE_WAY:
        for tx in range(x0, x1 + 1):
            plats["data"][_index(tx, ty, w)] = GID_ONEWAY
    # keep any other layers, but replace ground/platforms
    out_layers = []
    seen = set()
    for layer in src.get("layers") or []:
        name = layer.get("name")
        if name == "ground":
            out_layers.append(ground); seen.add("ground")
        elif name == "platforms":
            out_layers.append(plats); seen.add("platforms")
        else:
            out_layers.append(layer)
    if "ground" not in seen:
        out_layers.insert(0, ground)
    if "platforms" not in seen:
        out_layers.append(plats)
    src = dict(src)
    src["layers"] = out_layers
    src["width"] = w
    src["height"] = h
    src["tilewidth"] = TILE
    src["tileheight"] = TILE
    return src


def gap_records():
    """Takeoff is the centre of the last solid tile before each gap, 1 px above the floor."""
    recs = []
    for (a, b) in GAPS:
        # last solid tile is a-1; first solid after is b+1
        takeoff_tx = a - 1
        land_tx0, land_tx1 = b + 1, next(r[1] for r in SOLID if r[0] == b + 1)
        recs.append({
            "takeoff": [takeoff_tx * TILE + TILE / 2, FLOOR_Y * TILE - 1],
            "land_min": land_tx0 * TILE,
            "land_max": (land_tx1 + 1) * TILE,
            "floor_y": FLOOR_Y * TILE,
        })
    return recs


def cells_payload():
    spawn_x = SPAWN_TX * TILE + TILE / 2
    spawn_y = SPAWN_TY * TILE - HALF_H
    return {
        "tile": TILE,
        "spawn": {"x": spawn_x, "y": spawn_y},
        "gravity": GRAVITY,
        "jump_v": JUMP_V,
        "speed": SPEED,
        "gaps": gap_records(),
        "coin": {"x": 14 * TILE + TILE / 2, "y": FLOOR_Y * TILE - 8},
        "map": {"w": MAP_W, "h": MAP_H},
        "one_way": [{"x": x, "y": y} for x0, x1, y in ONE_WAY for x in range(x0, x1 + 1)],
        "verify_frames": 90,
    }


def check_arc(path: Path, land_min: float, land_max: float, floor_y: float) -> None:
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("out_of_bounds"):
        raise SystemExit(f"{path}: jump-arc left the map (out_of_bounds)")
    end = rec.get("end")
    if not (isinstance(end, list) and len(end) == 2):
        raise SystemExit(f"{path}: jump-arc JSON is missing end [x, y]")
    x, y = float(end[0]), float(end[1])
    if not rec.get("landed"):
        raise SystemExit(f"{path}: jump-arc did not land (end={end})")
    if x < land_min or x >= land_max:
        raise SystemExit(f"{path}: landing x={x} is not on the far platform [{land_min}, {land_max})")
    # landed in the floor row (allow a few px of sample overshoot into the tile)
    if y < floor_y - 1 or y >= floor_y + TILE + 1:
        raise SystemExit(f"{path}: landing y={y} is not on the floor row starting at {floor_y}")
    print(f"ok jump-arc {path.name}: end=({x}, {y}) on platform [{land_min}, {land_max})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bake platformer tiles and jump-gap metadata.")
    ap.add_argument("map", nargs="?", help="blank Tiled JSON from map-blank")
    ap.add_argument("-o", "--out", help="written Tiled JSON (default: overwrite is refused; use a new path)")
    ap.add_argument("--cells", help="Godot cells / physics JSON (default: next to --out as cells.json)")
    ap.add_argument("--check-arc", help="validate a jump-arc --json report against a platform")
    ap.add_argument("--land-min", type=float)
    ap.add_argument("--land-max", type=float)
    ap.add_argument("--floor-y", type=float, default=float(FLOOR_Y * TILE))
    args = ap.parse_args(argv)
    if args.check_arc:
        if args.land_min is None or args.land_max is None:
            raise SystemExit("--check-arc requires --land-min and --land-max")
        check_arc(Path(args.check_arc), args.land_min, args.land_max, args.floor_y)
        return 0
    if not args.map or not args.out:
        raise SystemExit("map and -o are required (or use --check-arc)")
    src = json.loads(Path(args.map).read_text(encoding="utf-8"))
    baked = build_map(src)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baked, indent=2), encoding="utf-8")
    cells_path = Path(args.cells) if args.cells else out.with_name("cells.json")
    cells_path.write_text(json.dumps(cells_payload(), indent=2), encoding="utf-8")
    print(f"baked {out} and {cells_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
