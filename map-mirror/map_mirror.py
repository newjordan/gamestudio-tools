#!/usr/bin/env python3
"""map-mirror: mirror a Tiled orthogonal JSON map horizontally or vertically.
Tile cells are repositioned and GID flip flags follow Tiled's flipHorizontally /
flipVertically rules (if the cell is already diagonally flipped, a horizontal
mirror toggles V instead of H, and a vertical mirror toggles H instead of V).
Axis-aligned objects are mirrored; polygon / polyline points are transformed in
world space; tile-object GIDs are flipped the same way as cells. Encoded data is
decoded. Two applications of the same axis are identity for cells, flags and
axis-aligned objects. Writes a new map; the input is never overwritten unless
`--in-place`. Infinite, hexagonal, isometric and staggered maps are refused.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
HFLIP = 0x80000000
VFLIP = 0x40000000
DFLIP = 0x20000000


def flags_of(gid):
    return (bool(gid & HFLIP), bool(gid & VFLIP), bool(gid & DFLIP))


def pack_flags(h, v, d):
    return (HFLIP if h else 0) | (VFLIP if v else 0) | (DFLIP if d else 0)


def flip_gid(gid, axis):
    """Tiled Cell::setFlippedHorizontally / Vertically."""
    if not gid:
        return 0
    tid = gid & MASK
    h, v, d = flags_of(gid)
    if axis == "h":
        if d:
            v = not v
        else:
            h = not h
    else:
        if d:
            h = not h
        else:
            v = not v
    return tid | pack_flags(h, v, d)


def dest_cell(x, y, w, h, axis):
    if axis == "h":
        return w - 1 - x, y
    return x, h - 1 - y


def flip_grid(data, w, h, axis):
    out = [0] * (w * h)
    for y in range(h):
        for x in range(w):
            nx, ny = dest_cell(x, y, w, h, axis)
            out[ny * w + nx] = flip_gid(data[y * w + x], axis)
    return out


def flip_point(px, py, map_w_px, map_h_px, axis):
    if axis == "h":
        return map_w_px - px, py
    return px, map_h_px - py


def mirror_object(obj, map_w_px, map_h_px, axis):
    obj = dict(obj)
    x, y = float(obj.get("x", 0)), float(obj.get("y", 0))
    w, h = float(obj.get("width", 0) or 0), float(obj.get("height", 0) or 0)
    rot = float(obj.get("rotation") or 0)
    if "polygon" in obj or "polyline" in obj:
        nx, ny = flip_point(x, y, map_w_px, map_h_px, axis)
        obj["x"], obj["y"] = nx, ny
        if rot:
            obj["rotation"] = -rot
        for key in ("polygon", "polyline"):
            if key in obj and isinstance(obj[key], list):
                new_pts = []
                for p in obj[key]:
                    lx, ly = float(p.get("x", 0)), float(p.get("y", 0))
                    gx, gy = flip_point(x + lx, y + ly, map_w_px, map_h_px, axis)
                    new_pts.append({"x": gx - obj["x"], "y": gy - obj["y"]})
                obj[key] = new_pts
    else:
        # axis-aligned box: move the origin so width/height still cover the mirrored AABB
        if axis == "h":
            obj["x"] = map_w_px - x - w
        else:
            obj["y"] = map_h_px - y - h
        if rot:
            obj["rotation"] = -rot
    if "gid" in obj and obj["gid"]:
        obj["gid"] = flip_gid(int(obj["gid"]), axis)
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


def mirror_map(m, axis):
    if axis not in ("h", "v"):
        raise SystemExit("--axis must be h or v")
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
            l["data"] = flip_grid(data, w, h, axis)
            l.pop("encoding", None)
            l.pop("compression", None)
        elif l.get("type") == "objectgroup" or "objects" in l:
            l["objects"] = [mirror_object(o, map_w_px, map_h_px, axis) for o in (l.get("objects") or [])]
        if "offsetx" in l or "offsety" in l:
            ox, oy = float(l.get("offsetx") or 0), float(l.get("offsety") or 0)
            if axis == "h":
                l["offsetx"], l["offsety"] = -ox, oy
            else:
                l["offsetx"], l["offsety"] = ox, -oy
        return l

    m = dict(m)
    m["layers"] = walk_layers(m.get("layers") or [], layer_fn)
    rec = {"axis": axis, "width": m["width"], "height": m["height"]}
    return m, rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mirror a Tiled orthogonal map horizontally or vertically.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--axis", choices=("h", "v"), required=True, help="h = horizontal, v = vertical")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    decoded = map_diff.decode_map(raw)
    m, rec = mirror_map(decoded, a.axis)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec["out"] = a.out
    print(f"mirrored {a.axis} -> {rec['width']}x{rec['height']} {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
