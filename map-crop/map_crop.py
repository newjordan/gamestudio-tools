#!/usr/bin/env python3
"""map-crop: crop a Tiled JSON map to the bounding box of used tiles (and optionally objects), plus a tile margin,
rewriting layer data and shifting objects so they stay aligned. Encoded tile data is decoded. Infinite maps: chunks
outside the crop are dropped and remaining chunks are shifted. The input is never overwritten.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tilemap-stats"))
import map_diff, tilemap_stats  # noqa: E402

MASK = tilemap_stats.MASK


def used_bbox(m, include_objects=True):
    tw, th = m.get("tilewidth", 16), m.get("tileheight", 16)
    xs, ys = [], []

    def walk(layers, ox=0, oy=0):
        for l in layers or []:
            typ = l.get("type")
            lx, ly = ox + l.get("x", 0), oy + l.get("y", 0)
            if typ == "group":
                walk(l.get("layers") or [], lx, ly); continue
            if typ == "tilelayer":
                if l.get("chunks"):
                    for c in l["chunks"]:
                        data, w, h, cx, cy = c.get("data") or [], c.get("width", 0), c.get("height", 0), c.get("x", 0), c.get("y", 0)
                        for i, g in enumerate(data):
                            if g & MASK:
                                xs.append(cx + (i % w)); ys.append(cy + (i // w))
                elif isinstance(l.get("data"), list):
                    w, h = l.get("width", m.get("width", 0)), l.get("height", m.get("height", 0))
                    for i, g in enumerate(l["data"]):
                        if g & MASK:
                            xs.append(lx + (i % w)); ys.append(ly + (i // w))
            elif typ == "objectgroup" and include_objects:
                for o in l.get("objects") or []:
                    xs.append((o.get("x", 0) + lx) / tw)
                    ys.append((o.get("y", 0) + ly) / th)
                    xs.append((o.get("x", 0) + o.get("width", 0) + lx) / tw)
                    ys.append((o.get("y", 0) + o.get("height", 0) + ly) / th)
    walk(m.get("layers") or [])
    if not xs: return 0, 0, int(m.get("width") or 1), int(m.get("height") or 1)
    x0, y0 = int(np_floor(min(xs))), int(np_floor(min(ys)))
    x1, y1 = int(np_ceil(max(xs) + (0 if max(xs) == int(max(xs)) and max(xs) in xs and False else 1))), int(np_ceil(max(ys) + 1))
    # for tiles, used cells are inclusive integers: bbox is min..max+1
    # for objects, we used /tw and included width so max is already an exclusive-ish float
    # Recompute tiles as inclusive:
    return x0, y0, x1, y1


def np_floor(v):
    import math; return math.floor(v)


def np_ceil(v):
    import math; return math.ceil(v)


def tile_bbox(m):
    xs, ys = [], []
    def walk(layers):
        for l in layers or []:
            if l.get("type") == "group": walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                if l.get("chunks"):
                    for c in l["chunks"]:
                        data, w, h, cx, cy = c.get("data") or [], c.get("width", 0), c.get("height", 0), c.get("x", 0), c.get("y", 0)
                        for i, g in enumerate(data):
                            if g & MASK:
                                xs.append(cx + (i % w)); ys.append(cy + (i // w))
                elif isinstance(l.get("data"), list):
                    w = l.get("width", m.get("width", 0))
                    for i, g in enumerate(l["data"]):
                        if g & MASK:
                            xs.append(i % w); ys.append(i // w)
    walk(m.get("layers") or [])
    if not xs: return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def object_bbox_tiles(m):
    tw, th = m.get("tilewidth", 16) or 16, m.get("tileheight", 16) or 16
    xs, ys = [], []
    def walk(layers):
        for l in layers or []:
            if l.get("type") == "group": walk(l.get("layers") or [])
            elif l.get("type") == "objectgroup":
                for o in l.get("objects") or []:
                    x, y = o.get("x", 0), o.get("y", 0)
                    w, h = o.get("width", 0) or 0, o.get("height", 0) or 0
                    xs.extend([x / tw, (x + w) / tw]); ys.extend([y / th, (y + h) / th])
    walk(m.get("layers") or [])
    if not xs: return None
    import math
    return int(math.floor(min(xs))), int(math.floor(min(ys))), int(math.ceil(max(xs))), int(math.ceil(max(ys)))


def crop_layer_data(data, src_w, src_h, x0, y0, cw, ch):
    out = []
    for y in range(ch):
        for x in range(cw):
            sx, sy = x + x0, y + y0
            if 0 <= sx < src_w and 0 <= sy < src_h:
                out.append(data[sy * src_w + sx])
            else:
                out.append(0)
    return out


def crop_map(m, margin=0, include_objects=True):
    m = map_diff.decode_map(m)
    tb = tile_bbox(m)
    ob = object_bbox_tiles(m) if include_objects else None
    boxes = [b for b in (tb, ob) if b]
    if not boxes:
        x0 = y0 = 0
        x1, y1 = int(m.get("width") or 1), int(m.get("height") or 1)
    else:
        x0 = min(b[0] for b in boxes) - margin
        y0 = min(b[1] for b in boxes) - margin
        x1 = max(b[2] for b in boxes) + margin
        y1 = max(b[3] for b in boxes) + margin
    # clamp to map bounds for finite maps; infinite maps may extend
    if not m.get("infinite"):
        x0 = max(0, x0); y0 = max(0, y0)
        x1 = min(int(m.get("width") or x1), x1); y1 = min(int(m.get("height") or y1), y1)
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)
    tw, th = m.get("tilewidth", 16), m.get("tileheight", 16)
    px, py = x0 * tw, y0 * th

    def walk(layers):
        for l in layers or []:
            typ = l.get("type")
            if typ == "group":
                walk(l.get("layers") or []); continue
            if typ == "tilelayer":
                if l.get("chunks"):
                    new = []
                    for c in l["chunks"]:
                        data, w, h, cx, cy = c.get("data") or [], c.get("width", 0), c.get("height", 0), c.get("x", 0), c.get("y", 0)
                        # keep chunk if it overlaps the crop, shift origin
                        if cx + w <= x0 or cy + h <= y0 or cx >= x0 + cw or cy >= y0 + ch:
                            continue
                        c = dict(c)
                        c["x"] = cx - x0; c["y"] = cy - y0
                        new.append(c)
                    l["chunks"] = new
                elif isinstance(l.get("data"), list):
                    sw, sh = l.get("width", m.get("width", cw)), l.get("height", m.get("height", ch))
                    l["data"] = crop_layer_data(l["data"], sw, sh, x0, y0, cw, ch)
                    l["width"], l["height"] = cw, ch
            elif typ == "objectgroup":
                for o in l.get("objects") or []:
                    o["x"] = o.get("x", 0) - px
                    o["y"] = o.get("y", 0) - py
            elif typ == "imagelayer":
                l["x"] = l.get("x", 0) - px
                l["y"] = l.get("y", 0) - py
    walk(m.get("layers") or [])
    m["width"], m["height"] = cw, ch
    return m, {"x": x0, "y": y0, "width": cw, "height": ch, "margin": margin}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Crop a Tiled JSON map to the used-tile bounding box plus margin.")
    ap.add_argument("map"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--margin", type=int, default=0)
    ap.add_argument("--tiles-only", action="store_true", help="ignore objects when computing the bbox")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.margin < 0: sys.exit("--margin must be >= 0")
    if os.path.abspath(a.out) == os.path.abspath(a.map) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    m, rec = crop_map(json.load(open(a.map, encoding="utf-8")), a.margin, include_objects=not a.tiles_only)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None), separators=(None if a.pretty else (",", ":")))
    rec["out"] = a.out
    print(f"crop {rec['width']}x{rec['height']} at ({rec['x']},{rec['y']}) -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
