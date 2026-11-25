#!/usr/bin/env python3
"""map-chunk: split a finite orthogonal Tiled JSON map into a grid of smaller maps
of `--size` tiles. Objects whose bounding box overlaps a chunk are copied and
shifted into that chunk's local origin. Optional `--world` writes a Tiled `.world`
index. Encoded tile data is decoded first. Infinite, isometric and hexagonal maps
are refused. The input is never overwritten unless `--in-place`.
"""
import argparse, os, copy, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def parse_size(s):
    parts = s.lower().replace(",", "x").split("x")
    if len(parts) != 2:
        raise SystemExit("--size must be WxH in tiles, e.g. 16x16")
    w, h = int(parts[0]), int(parts[1])
    if w < 1 or h < 1:
        raise SystemExit("--size values must be >= 1")
    return w, h


def obj_bbox(o):
    x, y = float(o.get("x") or 0), float(o.get("y") or 0)
    w, h = float(o.get("width") or 0), float(o.get("height") or 0)
    pts = []
    for key in ("polygon", "polyline"):
        for p in o.get(key) or []:
            pts.append((x + float(p.get("x") or 0), y + float(p.get("y") or 0)))
    if o.get("ellipse") or o.get("point") or (w == 0 and h == 0 and not pts):
        return x, y, x + max(w, 1e-6), y + max(h, 1e-6)
    if pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    return x, y, x + w, y + h


def shift_object(o, dx, dy):
    o = copy.deepcopy(o)
    o["x"] = float(o.get("x") or 0) - dx
    o["y"] = float(o.get("y") or 0) - dy
    return o


def slice_tile_layer(l, cx, cy, ww, hh):
    out = copy.deepcopy(l)
    out.pop("chunks", None)
    out["width"], out["height"] = ww, hh
    out["x"] = 0
    out["y"] = 0
    data = l.get("data") or []
    lw, lh = int(l.get("width") or 0), int(l.get("height") or 0)
    rows = []
    for y in range(cy, cy + hh):
        for x in range(cx, cx + ww):
            if 0 <= y < lh and 0 <= x < lw and y * lw + x < len(data):
                rows.append(int(data[y * lw + x]))
            else:
                rows.append(0)
    out["data"] = rows
    out.pop("encoding", None)
    out.pop("compression", None)
    return out


def walk_layers(layers, cx, cy, ww, hh, ox, oy, cw_px, ch_px):
    out = []
    for l in layers or []:
        typ = l.get("type")
        if typ == "group":
            g = copy.deepcopy(l)
            g["layers"] = walk_layers(l.get("layers") or [], cx, cy, ww, hh, ox, oy, cw_px, ch_px)
            out.append(g)
        elif typ == "tilelayer":
            if "chunks" in l:
                raise SystemExit("infinite (chunked) maps are refused; run tmx-infinite-to-finite first")
            out.append(slice_tile_layer(l, cx, cy, ww, hh))
        elif typ == "objectgroup":
            g = copy.deepcopy(l)
            kept = []
            for o in l.get("objects") or []:
                x0, y0, x1, y1 = obj_bbox(o)
                if x1 <= ox or y1 <= oy or x0 >= ox + cw_px or y0 >= oy + ch_px:
                    continue
                kept.append(shift_object(o, ox, oy))
            g["objects"] = kept
            out.append(g)
        elif typ == "imagelayer":
            g = copy.deepcopy(l)
            g["x"] = float(l.get("x") or 0) - ox
            g["y"] = float(l.get("y") or 0) - oy
            out.append(g)
        else:
            out.append(copy.deepcopy(l))
    return out


def chunk_map(m, cw, ch):
    ori = (m.get("orientation") or "orthogonal").lower()
    if ori != "orthogonal":
        raise SystemExit(f"{ori} maps are refused (orthogonal finite only)")
    if m.get("infinite"):
        raise SystemExit("infinite maps are refused; run tmx-infinite-to-finite first")
    m = map_diff.decode_map(copy.deepcopy(m))
    W, H = int(m["width"]), int(m["height"])
    tw, th = int(m.get("tilewidth") or 16), int(m.get("tileheight") or 16)
    pieces = []
    for cy in range(0, H, ch):
        for cx in range(0, W, cw):
            ww, hh = min(cw, W - cx), min(ch, H - cy)
            ox, oy = cx * tw, cy * th
            part = copy.deepcopy(m)
            part["width"], part["height"] = ww, hh
            part["layers"] = walk_layers(m.get("layers") or [], cx, cy, ww, hh, ox, oy, ww * tw, hh * th)
            props = list(part.get("properties") or [])
            props = [p for p in props if p.get("name") not in ("chunk_x", "chunk_y")]
            props += [{"name": "chunk_x", "type": "int", "value": cx},
                      {"name": "chunk_y", "type": "int", "value": cy}]
            part["properties"] = props
            pieces.append({"cx": cx, "cy": cy, "width": ww, "height": hh, "map": part})
    return pieces, tw, th


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a finite orthogonal Tiled map into a grid of chunk maps.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True, help="output directory")
    ap.add_argument("--size", default="16x16", help="chunk size in tiles, WxH (default 16x16)")
    ap.add_argument("--prefix", default="chunk", help="filename prefix (default: chunk)")
    ap.add_argument("--world", help="write a Tiled .world index at this path")
    ap.add_argument("--json", help="report path")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.world:
        safe_out.check(a.map, a.world, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    cw, ch = parse_size(a.size)
    raw = json.load(open(a.map, encoding="utf-8"))
    pieces, tw, th = chunk_map(raw, cw, ch)
    os.makedirs(a.out, exist_ok=True)
    world_maps = []
    files = []
    for p in pieces:
        name = f"{a.prefix}_{p['cx']}_{p['cy']}.json"
        dest = os.path.join(a.out, name)
        json.dump(p["map"], open(dest, "w"), indent=2)
        files.append(name)
        world_maps.append({
            "fileName": name,
            "x": p["cx"] * tw, "y": p["cy"] * th,
            "width": p["width"] * tw, "height": p["height"] * th,
        })
    if a.world:
        os.makedirs(os.path.dirname(os.path.abspath(a.world)) or ".", exist_ok=True)
        json.dump({"type": "world", "maps": world_maps}, open(a.world, "w"), indent=2)
    rec = {"chunks": len(pieces), "size": [cw, ch], "files": files, "out": a.out,
           "world": a.world}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(pieces)} chunk(s) of {cw}x{ch} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
