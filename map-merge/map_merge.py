#!/usr/bin/env python3
"""map-merge: merge layers and objects from several Tiled JSON maps (same tile size) into one.
Each source can take a name prefix (--prefix, repeatable in file order, or the default is the stem plus '_')
and a tile offset (--offset X,Y, repeatable; missing offsets are 0,0). The output map grows to the bounding box
of every shifted source. Tilesets with the same source/image/name are reused (GIDs remapped); new tilesets are
appended with a fresh firstgid. Encoded tile data is decoded to arrays. Object and layer ids are made unique.
Refuses to overwrite an input path.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLAGS = 0xE0000000


def parse_xy(s):
    a, b = s.replace("x", ",").split(","); return int(a), int(b)


def ts_key(ts):
    return (ts.get("source") or ts.get("image") or ts.get("name") or "", ts.get("tilewidth"), ts.get("tileheight"))


def gid_map_for(src_sets, dest_sets, assigned):
    """Map unflagged source gid -> dest gid. assigned is {key: firstgid} already in dest_sets."""
    table = {}
    next_fg = max((t.get("firstgid", 1) + t.get("tilecount", 1) for t in dest_sets), default=1)
    for ts in src_sets:
        key, fg = ts_key(ts), ts.get("firstgid", 1)
        count = ts.get("tilecount") or 1
        if key in assigned:
            dest_fg = assigned[key]
        else:
            dest_fg = next_fg; next_fg = dest_fg + count
            nxt = dict(ts); nxt["firstgid"] = dest_fg; dest_sets.append(nxt); assigned[key] = dest_fg
        for loc in range(count):
            table[fg + loc] = dest_fg + loc
    return table


def remap_gids(data, table):
    out = []
    for g in data:
        gid, flags = g & MASK, g & FLAGS
        out.append((table.get(gid, gid) | flags) if gid else 0)
    return out


def stamp_layer(data, sw, sh, dw, dh, ox, oy, table):
    out = [0] * (dw * dh)
    for i, g in enumerate(data):
        x, y = i % sw, i // sw
        nx, ny = x + ox, y + oy
        if 0 <= nx < dw and 0 <= ny < dh:
            gid, flags = g & MASK, g & FLAGS
            ng = table.get(gid, gid) if gid else 0
            out[ny * dw + nx] = (ng | flags) if ng else 0
    return out


def shift_layers(layers, ox, oy, tw, th, sw, sh, dw, dh, table, prefix, ids, obj_ids):
    out = []
    for l in layers or []:
        l = dict(l)
        if prefix: l["name"] = prefix + l.get("name", "")
        if "id" in l: l["id"] = next(ids)
        typ = l.get("type")
        if typ == "group":
            l["layers"] = shift_layers(l.get("layers") or [], ox, oy, tw, th, sw, sh, dw, dh, table, "", ids, obj_ids)
        elif typ == "tilelayer":
            l["width"], l["height"] = dw, dh
            if "chunks" in l:
                # flatten chunks into a finite layer at the destination size
                cells = {}
                for c in l["chunks"]:
                    data = map_diff.layer_gids(l, c)
                    for i, g in enumerate(data):
                        cells[(c["x"] + i % c["width"] + ox, c["y"] + i // c["width"] + oy)] = g
                arr = [0] * (dw * dh)
                for (x, y), g in cells.items():
                    if 0 <= x < dw and 0 <= y < dh:
                        gid, flags = g & MASK, g & FLAGS
                        ng = table.get(gid, gid) if gid else 0
                        arr[y * dw + x] = (ng | flags) if ng else 0
                l["data"] = arr; del l["chunks"]
            else:
                l["data"] = stamp_layer(map_diff.layer_gids(l), sw, sh, dw, dh, ox, oy, table)
            l.pop("encoding", None); l.pop("compression", None)
        elif typ == "objectgroup":
            objs = []
            for o in l.get("objects") or []:
                o = dict(o); o["x"] = o.get("x", 0) + ox * tw; o["y"] = o.get("y", 0) + oy * th
                o["id"] = next(obj_ids)
                if o.get("gid"):
                    g = o["gid"]; gid, flags = g & MASK, g & FLAGS
                    ng = table.get(gid, gid) if gid else 0
                    o["gid"] = (ng | flags) if ng else 0
                if prefix and o.get("name"): o["name"] = prefix + o["name"]
                objs.append(o)
            l["objects"] = objs
        elif typ == "imagelayer":
            l["offsetx"] = l.get("offsetx", 0) + ox * tw
            l["offsety"] = l.get("offsety", 0) + oy * th
        out.append(l)
    return out


def merge(paths, prefixes, offsets, name="merged"):
    maps = []
    for p in paths:
        m = map_diff.decode_map(json.load(open(p)))
        if m.get("orientation", "orthogonal") != "orthogonal":
            raise SystemExit(f"{p}: only orthogonal maps are supported")
        maps.append((p, m))
    tw, th = maps[0][1]["tilewidth"], maps[0][1]["tileheight"]
    for p, m in maps:
        if m["tilewidth"] != tw or m["tileheight"] != th:
            raise SystemExit(f"{p}: tile size {m['tilewidth']}x{m['tileheight']} != {tw}x{th}")
    # bounding box in tiles
    boxes = []
    for i, (p, m) in enumerate(maps):
        ox, oy = offsets[i] if i < len(offsets) else (0, 0)
        boxes.append((ox, oy, ox + m["width"], oy + m["height"]))
    minx, miny = min(b[0] for b in boxes), min(b[1] for b in boxes)
    maxx, maxy = max(b[2] for b in boxes), max(b[3] for b in boxes)
    # shift so origin is 0,0
    adj = [((ox - minx), (oy - miny)) for ox, oy, _, _ in boxes]
    dw, dh = maxx - minx, maxy - miny
    dest_sets, assigned, layers = [], {}, []
    ids = iter(range(1, 10 ** 6)); obj_ids = iter(range(1, 10 ** 6))
    for i, (p, m) in enumerate(maps):
        table = gid_map_for(m.get("tilesets") or [], dest_sets, assigned)
        pref = prefixes[i] if i < len(prefixes) else (os.path.splitext(os.path.basename(p))[0] + "_")
        ox, oy = adj[i]
        layers.extend(shift_layers(m.get("layers") or [], ox, oy, tw, th, m["width"], m["height"], dw, dh, table, pref, ids, obj_ids))
    out = {"type": "map", "version": maps[0][1].get("version", "1.10"), "orientation": "orthogonal",
           "width": dw, "height": dh, "tilewidth": tw, "tileheight": th, "infinite": False,
           "renderorder": maps[0][1].get("renderorder", "right-down"), "tilesets": dest_sets, "layers": layers}
    if name: out["name"] = name
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge Tiled JSON maps into one.")
    ap.add_argument("maps", nargs="+"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--prefix", action="append", default=[], help="layer/object name prefix, one per map (default: stem_)")
    ap.add_argument("--offset", action="append", default=[], help="tile offset X,Y, one per map (default 0,0)")
    ap.add_argument("--name", default="merged"); ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    for p in a.maps:
        if os.path.abspath(a.out) == os.path.abspath(p) and not a.in_place:
            sys.exit("refusing to overwrite an input map; pick a different -o or pass --in-place")
    offsets = [parse_xy(s) for s in a.offset]
    m = merge(a.maps, a.prefix, offsets, a.name)
    json.dump(m, open(a.out, "w"), indent=2 if a.pretty else None, separators=None if a.pretty else (",", ":"))
    print(f"{len(a.maps)} map(s) -> {m['width']}x{m['height']}, {len(m['layers'])} layer(s), {len(m['tilesets'])} tileset(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
