#!/usr/bin/env python3
"""map-rotate: rotate a Tiled orthogonal JSON map by 90, 180 or 270 degrees clockwise.
Tile cells move with the layer (width and height swap on 90/270) and GID flip flags are
updated so tiles stay visually aligned. Orthogonal rectangle objects are moved and have
their width/height swapped as needed; `rotation` is increased by the same angle. Encoded
data is decoded. Writes a new map; the input is never overwritten unless `--in-place`.
Infinite, hexagonal, isometric and staggered maps are refused.
"""
import argparse, os, json, math, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
HFLIP = 0x80000000
VFLIP = 0x40000000
DFLIP = 0x20000000

# (h, v, d) -> after one 90-degree clockwise tile rotation
# Identity cycles: I -> HD -> HV -> VD -> I
# Flipped cycles:  H -> HVD -> V -> D -> H
ROT90 = {
    (0, 0, 0): (1, 0, 1),
    (1, 0, 1): (1, 1, 0),
    (1, 1, 0): (0, 1, 1),
    (0, 1, 1): (0, 0, 0),
    (1, 0, 0): (1, 1, 1),
    (1, 1, 1): (0, 1, 0),
    (0, 1, 0): (0, 0, 1),
    (0, 0, 1): (1, 0, 0),
}


def flags_of(gid):
    return (bool(gid & HFLIP), bool(gid & VFLIP), bool(gid & DFLIP))


def pack_flags(h, v, d):
    return (HFLIP if h else 0) | (VFLIP if v else 0) | (DFLIP if d else 0)


def rot_gid(gid, times):
    if not gid:
        return 0
    tid = gid & MASK
    st = flags_of(gid)
    for _ in range(times % 4):
        st = ROT90[st]
    return tid | pack_flags(*st)


def dest_cell(x, y, w, h, times):
    times = times % 4
    if times == 0:
        return x, y, w, h
    if times == 1:  # 90 CW
        return h - 1 - y, x, h, w
    if times == 2:
        return w - 1 - x, h - 1 - y, w, h
    # 270 CW
    return y, w - 1 - x, h, w


def rotate_grid(data, w, h, times):
    times = times % 4
    if times == 0:
        return data, w, h
    _, _, nw, nh = dest_cell(0, 0, w, h, times)
    out = [0] * (nw * nh)
    for y in range(h):
        for x in range(w):
            nx, ny, _, _ = dest_cell(x, y, w, h, times)
            out[ny * nw + nx] = rot_gid(data[y * w + x], times)
    return out, nw, nh


def rotate_point(px, py, map_w_px, map_h_px, times):
    times = times % 4
    if times == 0:
        return px, py
    if times == 1:
        return map_h_px - py, px
    if times == 2:
        return map_w_px - px, map_h_px - py
    return py, map_w_px - px


def rotate_object(obj, map_w_px, map_h_px, times):
    obj = dict(obj)
    x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
    w, h = float(obj.get("width", 0) or 0), float(obj.get("height", 0) or 0)
    times = times % 4
    # rotate the four corners of the axis-aligned box, then take the new AABB origin
    corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    rot = [rotate_point(cx, cy, map_w_px, map_h_px, times) for cx, cy in corners]
    xs, ys = [p[0] for p in rot], [p[1] for p in rot]
    obj["x"] = min(xs)
    obj["y"] = min(ys)
    if times in (1, 3):
        obj["width"] = h
        obj["height"] = w
    else:
        obj["width"] = w
        obj["height"] = h
    if "rotation" in obj or times:
        obj["rotation"] = (float(obj.get("rotation") or 0) + 90 * times) % 360
    # polygon / polyline points are relative to the object origin; a 90 CW of the
    # map also rotates those local points (and the origin moved to the new AABB min).
    origin_rot = rotate_point(x, y, map_w_px, map_h_px, times)
    for key in ("polygon", "polyline"):
        if key in obj and isinstance(obj[key], list):
            new_pts = []
            for p in obj[key]:
                lx, ly = float(p.get("x", 0)), float(p.get("y", 0))
                gx, gy = rotate_point(x + lx, y + ly, map_w_px, map_h_px, times)
                new_pts.append({"x": gx - obj["x"], "y": gy - obj["y"]})
            obj[key] = new_pts
    return obj


def walk_layers(layers, fn):
    out = []
    for l in layers or []:
        l = dict(l)
        if l.get("type") == "group":
            l["layers"] = walk_layers(l.get("layers") or [], fn)
            out.append(l)
        else:
            out.append(fn(l))
    return out


def rotate_map(m, degrees):
    if degrees % 90:
        raise SystemExit("--degrees must be a multiple of 90")
    times = (degrees // 90) % 4
    if m.get("infinite"):
        raise SystemExit("infinite maps are refused; run tmx-infinite-to-finite first")
    orient = (m.get("orientation") or "orthogonal").lower()
    if orient != "orthogonal":
        raise SystemExit(f"orientation {orient!r} is not supported (orthogonal only)")
    tw, th = int(m.get("tilewidth") or 0), int(m.get("tileheight") or 0)
    mw, mh = int(m["width"]), int(m["height"])
    map_w_px, map_h_px = mw * tw, mh * th

    def layer_fn(l):
        l = dict(l)
        if l.get("type") == "tilelayer":
            if l.get("infinite") or "chunks" in l:
                raise SystemExit("infinite layers are refused")
            w, h = int(l.get("width") or mw), int(l.get("height") or mh)
            data = list(l.get("data") or [])
            if len(data) != w * h:
                raise SystemExit(f"layer {l.get('name')!r} data length {len(data)} != {w}x{h}")
            data, nw, nh = rotate_grid(data, w, h, times)
            l["data"] = data
            l["width"], l["height"] = nw, nh
            l.pop("encoding", None)
            l.pop("compression", None)
            if "offsetx" in l or "offsety" in l:
                ox, oy = float(l.get("offsetx") or 0), float(l.get("offsety") or 0)
                nx, ny = rotate_point(ox, oy, map_w_px, map_h_px, times)
                l["offsetx"], l["offsety"] = nx, ny
        elif l.get("type") == "objectgroup" or "objects" in l:
            objs = [rotate_object(o, map_w_px, map_h_px, times) for o in (l.get("objects") or [])]
            l["objects"] = objs
        if times in (1, 3) and l.get("type") in ("imagelayer",):
            # image layers keep their image; offset is rotated above if present
            pass
        return l

    m = dict(m)
    m["layers"] = walk_layers(m.get("layers") or [], layer_fn)
    if times in (1, 3):
        m["width"], m["height"] = mh, mw
    rec = {"degrees": times * 90, "width": m["width"], "height": m["height"]}
    return m, rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rotate a Tiled orthogonal map by 90, 180 or 270 degrees clockwise.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--degrees", type=int, required=True, help="90, 180 or 270 (or a multiple of 90)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    decoded = map_diff.decode_map(raw)
    m, rec = rotate_map(decoded, a.degrees)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec["out"] = a.out
    print(f"rotated {rec['degrees']} CW -> {rec['width']}x{rec['height']} {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
