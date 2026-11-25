#!/usr/bin/env python3
"""tmx-infinite-to-finite: convert a Tiled infinite (chunked) JSON map to a finite array map.
Chunks are decoded, a bounding box is taken from used cells (plus `--margin`, or an explicit
`--origin` / `--size`), and each tile layer becomes a plain `data` array. Object positions are
not shifted (they stay in world pixels); pass `--shift-objects` to subtract the new origin.
Writes a new map; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def walk_tile_layers(layers):
    for l in layers or []:
        if l.get("type") == "group":
            yield from walk_tile_layers(l.get("layers") or [])
        elif l.get("type") == "tilelayer":
            yield l


def used_bounds(m):
    xs, ys = [], []
    for l in walk_tile_layers(m.get("layers") or []):
        if "chunks" in l:
            for c in l["chunks"]:
                w, h, data = c["width"], c["height"], c.get("data") or []
                for i, g in enumerate(data):
                    if g:
                        xs.append(c["x"] + i % w)
                        ys.append(c["y"] + i // w)
        else:
            w = l.get("width") or m.get("width") or 0
            data = l.get("data") or []
            sx, sy = l.get("startx", 0), l.get("starty", 0)
            for i, g in enumerate(data):
                if g:
                    xs.append(sx + i % w)
                    ys.append(sy + i // w)
    if not xs:
        return 0, 0, m.get("width") or 1, m.get("height") or 1
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def flatten_layer(l, ox, oy, w, h):
    data = [0] * (w * h)
    if "chunks" in l:
        for c in l["chunks"]:
            cw, ch, cd = c["width"], c["height"], c.get("data") or []
            for i, g in enumerate(cd):
                if not g:
                    continue
                x, y = c["x"] + i % cw - ox, c["y"] + i // cw - oy
                if 0 <= x < w and 0 <= y < h:
                    data[y * w + x] = int(g)
    else:
        lw = l.get("width") or w
        sx, sy = l.get("startx", 0) - ox, l.get("starty", 0) - oy
        for i, g in enumerate(l.get("data") or []):
            if not g:
                continue
            x, y = sx + i % lw, sy + i // lw
            if 0 <= x < w and 0 <= y < h:
                data[y * w + x] = int(g)
    out = dict(l)
    out["width"] = w
    out["height"] = h
    out["data"] = data
    out.pop("chunks", None)
    out.pop("startx", None)
    out.pop("starty", None)
    out.pop("encoding", None)
    out.pop("compression", None)
    return out


def shift_objects(layers, dx, dy, tw, th):
    for l in layers or []:
        if l.get("type") == "group":
            shift_objects(l.get("layers") or [], dx, dy, tw, th)
        elif l.get("type") == "objectgroup":
            for o in l.get("objects") or []:
                if "x" in o:
                    o["x"] = o["x"] - dx * tw
                if "y" in o:
                    o["y"] = o["y"] - dy * th


def rewrite_layers(layers, ox, oy, w, h):
    out = []
    for l in layers or []:
        if l.get("type") == "group":
            g = dict(l)
            g["layers"] = rewrite_layers(l.get("layers") or [], ox, oy, w, h)
            out.append(g)
        elif l.get("type") == "tilelayer":
            out.append(flatten_layer(l, ox, oy, w, h))
        else:
            out.append(dict(l))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert a Tiled infinite (chunked) map to a finite array map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--origin", help="X,Y of the finite map's top-left in tile coordinates (default: used-cell bbox)")
    ap.add_argument("--size", help="W,H of the finite map in tiles (default: used-cell bbox)")
    ap.add_argument("--margin", type=int, default=0, help="tiles of padding around the used-cell bbox")
    ap.add_argument("--shift-objects", action="store_true",
                    help="subtract the new origin (in pixels) from every object position")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    ux0, uy0, ux1, uy1 = used_bounds(m)
    if a.origin:
        parts = a.origin.split(",")
        if len(parts) != 2:
            sys.exit("--origin must be X,Y")
        ox, oy = int(parts[0]), int(parts[1])
    else:
        ox, oy = ux0 - a.margin, uy0 - a.margin
    if a.size:
        parts = a.size.split(",")
        if len(parts) != 2:
            sys.exit("--size must be W,H")
        w, h = int(parts[0]), int(parts[1])
    else:
        w, h = (ux1 + a.margin) - ox, (uy1 + a.margin) - oy
    if w <= 0 or h <= 0:
        sys.exit(f"finite size must be positive, got {w}x{h}")
    m["layers"] = rewrite_layers(m.get("layers") or [], ox, oy, w, h)
    if a.shift_objects:
        shift_objects(m["layers"], ox, oy, m.get("tilewidth") or 16, m.get("tileheight") or 16)
    m["infinite"] = False
    m["width"] = w
    m["height"] = h
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"origin": [ox, oy], "width": w, "height": h, "used": [ux0, uy0, ux1, uy1], "out": a.out}
    print(f"finite {w}x{h} at origin {ox},{oy} -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
