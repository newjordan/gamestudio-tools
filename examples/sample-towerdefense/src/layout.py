#!/usr/bin/env python3
"""Check the painted causeway and add its object layer.

map-fill paints grass, water and the road. This script checks that the path
cells are exactly the waypoint polyline, that every planned tower sits on
grass off the road, then writes the core tile and the Tiled objects
(spawn, core, waypoints, rooms, portals, the route polyline).
"""
import argparse, csv, json, os


def layer(m, name):
    for item in m["layers"]:
        if item.get("name") == name:
            return item
    raise SystemExit("missing layer %s" % name)


def cells_of(wps):
    seen, cells = set(), []
    for (x0, y0), (x1, y1) in zip(wps, wps[1:]):
        if x0 != x1 and y0 != y1:
            raise SystemExit("waypoint segment %s -> %s is not axis-aligned" % ((x0, y0), (x1, y1)))
        dx = 0 if x0 == x1 else (1 if x1 > x0 else -1)
        dy = 0 if y0 == y1 else (1 if y1 > y0 else -1)
        x, y = x0, y0
        while True:
            if (x, y) not in seen:
                seen.add((x, y))
                cells.append((x, y))
            if (x, y) == (x1, y1):
                break
            x += dx
            y += dy
    return seen


def prop(name, value):
    kind = "int" if isinstance(value, int) else "string"
    return {"name": name, "type": kind, "value": value}


def point(items, name, typ, x, y, **props):
    obj = {"id": len(items) + 1, "name": name, "type": typ, "point": True, "rotation": 0,
           "visible": True, "x": x, "y": y, "width": 0, "height": 0}
    if props:
        obj["properties"] = [prop(k, v) for k, v in props.items()]
    items.append(obj)


def rect_obj(items, name, typ, x, y, w, h, **props):
    obj = {"id": len(items) + 1, "name": name, "type": typ, "rotation": 0, "visible": True,
           "x": x, "y": y, "width": w, "height": h}
    if props:
        obj["properties"] = [prop(k, v) for k, v in props.items()]
    items.append(obj)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--build", required=True)
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding="utf-8"))
    m = json.load(open(a.map, encoding="utf-8"))
    w, h = m["width"], m["height"]
    tile = rules["tile"]
    if (w, h) != (rules["width"], rules["height"]) or m["tilewidth"] != tile:
        raise SystemExit("map size does not match rules.json")
    wps = [tuple(p) for p in rules["waypoints"]]
    path_cells = cells_of(wps)
    ground = layer(m, "ground")["data"]
    path = layer(m, "path")
    pdata = path["data"]
    if len(ground) != w * h or len(pdata) != w * h:
        raise SystemExit("layer data length is not %d x %d" % (w, h))
    for x, y in path_cells:
        if pdata[y * w + x] != 2:
            raise SystemExit("path cell %d,%d is gid %s, expected 2" % (x, y, pdata[y * w + x]))
        if ground[y * w + x] == 3:
            raise SystemExit("water covers the road at %d,%d" % (x, y))
    for i, gid in enumerate(pdata):
        if gid and (i % w, i // w) not in path_cells:
            raise SystemExit("unexpected path gid at %d,%d" % (i % w, i // w))
    core = tuple(wps[-1])
    pdata[core[1] * w + core[0]] = 4
    with open(a.build, newline="", encoding="utf-8") as fh:
        builds = list(csv.DictReader(fh))
    for row in builds:
        x, y = int(row["x"]), int(row["y"])
        if (x, y) in path_cells or pdata[y * w + x]:
            raise SystemExit("tower %s is on the road at %d,%d" % (row["kind"], x, y))
        if ground[y * w + x] != 1:
            raise SystemExit("tower %s is not on grass at %d,%d (gid %s)" % (row["kind"], x, y, ground[y * w + x]))
    pts = [tuple(p) for p in rules["points"]]
    if len(pts) != len(wps):
        raise SystemExit("points and waypoints differ in length")
    items = []
    point(items, "spawn", "spawn", pts[0][0], pts[0][1])
    point(items, "core", "core", pts[-1][0], pts[-1][1])
    for i, (px, py) in enumerate(pts):
        point(items, "wp%d" % i, "waypoint", px, py, order=i)
    # Rooms cover a portal each. Coordinates are pixels, y-down, matching Tiled.
    rect_obj(items, "gate", "room", 0, 16, 96, 48, seg="gate")
    rect_obj(items, "bend", "room", 208, 80, 64, 48, seg="bend")
    rect_obj(items, "mill", "room", 256, 128, 64, 48, seg="mill")
    point(items, "to_bend", "portal", 40, 40, target="bend")
    point(items, "to_mill", "portal", 248, 104, target="mill")
    route = {"id": len(items) + 1, "name": "route", "type": "route", "rotation": 0, "visible": True,
             "x": pts[0][0], "y": pts[0][1], "width": 0, "height": 0,
             "polyline": [{"x": px - pts[0][0], "y": py - pts[0][1]} for px, py in pts]}
    items.append(route)
    next_id = max(layer_item["id"] for layer_item in m["layers"]) + 1
    m["layers"].append({
        "type": "objectgroup", "id": next_id, "name": "objects", "visible": True, "opacity": 1,
        "x": 0, "y": 0, "draworder": "topdown", "objects": items,
    })
    m["nextlayerid"] = next_id + 1
    m["nextobjectid"] = len(items) + 1
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    print("causeway %d path cells, %d objects -> %s" % (len(path_cells), len(items), a.out))


if __name__ == "__main__":
    main()
