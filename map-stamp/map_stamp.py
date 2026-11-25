#!/usr/bin/env python3
"""map-stamp: stamp a prefab Tiled JSON (tile layers and/or objects) onto a target map at a tile (or pixel) position.
The prefab may be a small map or a file whose only content is an object group. Prefab tilesets are merged into the
target (same rules as map-merge: reuse a matching source/image/name, otherwise append and remap GIDs). Tile cells
overwrite by default; --empty-only writes only onto empty cells. Objects are copied with new ids and a name prefix.
Writes a new map; refuses to overwrite the target. Encoded tile data is decoded.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-merge"))
import map_diff, map_merge  # noqa: E402

MASK, FLAGS = map_merge.MASK, map_merge.FLAGS


def max_ids(m):
    lid, oid = 0, 0
    def walk(ls):
        nonlocal lid, oid
        for l in ls or []:
            lid = max(lid, l.get("id") or 0)
            if l.get("type") == "group": walk(l.get("layers") or [])
            if l.get("type") == "objectgroup":
                for o in l.get("objects") or []: oid = max(oid, o.get("id") or 0)
    walk(m.get("layers") or []); return lid, oid


def find_or_add_layer(m, typ, name, ids):
    for l in m.get("layers") or []:
        if l.get("type") == typ and l.get("name") == name: return l
    l = {"id": next(ids), "name": name, "type": typ, "visible": True,
         "width": m["width"], "height": m["height"]} if typ == "tilelayer" else {"id": next(ids), "name": name, "type": typ, "objects": []}
    if typ == "tilelayer": l["data"] = [0] * (m["width"] * m["height"])
    m.setdefault("layers", []).append(l)
    return l


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stamp a Tiled prefab onto a target map.")
    ap.add_argument("target"); ap.add_argument("--prefab", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--at", default="0,0", help="tile offset X,Y")
    ap.add_argument("--at-px", help="pixel offset X,Y (overrides --at)")
    ap.add_argument("--empty-only", action="store_true")
    ap.add_argument("--objects-only", action="store_true"); ap.add_argument("--tiles-only", action="store_true")
    ap.add_argument("--layer", help="tile-layer name to stamp into (default: a new layer named after the prefab)")
    ap.add_argument("--object-layer", help="object-layer name to stamp into (default: a new layer named after the prefab)")
    ap.add_argument("--prefix", default=""); ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) in {os.path.abspath(a.target), os.path.abspath(a.prefab)}:
        sys.exit("refusing to overwrite an input; pick a different -o or pass --in-place")
    dest = map_diff.decode_map(json.load(open(a.target)))
    pref = map_diff.decode_map(json.load(open(a.prefab)))
    if pref.get("tilewidth") and dest.get("tilewidth") and (pref["tilewidth"] != dest["tilewidth"] or pref["tileheight"] != dest["tileheight"]):
        sys.exit("prefab tile size does not match the target")
    tw, th = dest["tilewidth"], dest["tileheight"]
    if a.at_px:
        px, py = map_merge.parse_xy(a.at_px); ox, oy = int(px // tw), int(py // th)
        obj_dx, obj_dy = px, py
    else:
        ox, oy = map_merge.parse_xy(a.at); obj_dx, obj_dy = ox * tw, oy * th
    assigned = {map_merge.ts_key(ts): ts.get("firstgid", 1) for ts in dest.get("tilesets") or []}
    table = map_merge.gid_map_for(pref.get("tilesets") or [], dest.setdefault("tilesets", []), assigned)
    lid, oid = max_ids(dest)
    ids = iter(range(lid + 1, 10 ** 6)); obj_ids = iter(range(oid + 1, 10 ** 6))
    stem = os.path.splitext(os.path.basename(a.prefab))[0]
    tiled, objed = 0, 0
    dw, dh = dest["width"], dest["height"]
    for name, l in map_diff.flat_layers(pref.get("layers") or []):
        typ = l.get("type")
        if typ == "tilelayer" and not a.objects_only:
            target = find_or_add_layer(dest, "tilelayer", a.layer or stem, ids)
            # if the existing layer has no data array yet
            if "data" not in target or not isinstance(target.get("data"), list):
                target["data"] = map_diff.layer_gids(target) or [0] * (dw * dh)
                target["width"], target["height"] = dw, dh
            data = map_merge.remap_gids(map_diff.layer_gids(l), table)
            sw, sh = l.get("width") or pref.get("width") or 0, l.get("height") or pref.get("height") or 0
            for i, g in enumerate(data):
                if not (g & MASK): continue
                x, y = (i % sw) + ox, (i // sw) + oy
                if not (0 <= x < dw and 0 <= y < dh): continue
                di = y * dw + x
                if a.empty_only and (target["data"][di] & MASK): continue
                target["data"][di] = g; tiled += 1
        elif typ == "objectgroup" and not a.tiles_only:
            target = find_or_add_layer(dest, "objectgroup", a.object_layer or (a.layer or stem + "_obj"), ids)
            target.setdefault("objects", [])
            for o in l.get("objects") or []:
                o = dict(o); o["x"] = o.get("x", 0) + obj_dx; o["y"] = o.get("y", 0) + obj_dy
                o["id"] = next(obj_ids)
                if o.get("gid"):
                    g = o["gid"]; gid, flags = g & MASK, g & FLAGS
                    ng = table.get(gid, gid) if gid else 0
                    o["gid"] = (ng | flags) if ng else 0
                if a.prefix and o.get("name"): o["name"] = a.prefix + o["name"]
                target["objects"].append(o); objed += 1
    json.dump(dest, open(a.out, "w"), indent=2 if a.pretty else None, separators=None if a.pretty else (",", ":"))
    print(f"stamped {tiled} tile(s), {objed} object(s) at ({ox}, {oy}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
