#!/usr/bin/env python3
"""map-scale: scale a Tiled orthogonal finite map's tile size and pixel coordinates.
`--factor` multiplies tilewidth / tileheight; `--tile W` or `--tile WxH` sets them
absolutely (one of the two is required). Object x/y/width/height, polygon and polyline
points, layer offsets and image-layer positions are scaled by the same ratios so they
stay aligned with the tiles. Tile GIDs and the map size in tiles are unchanged.
Infinite, hexagonal and isometric maps are refused. The input is never overwritten
unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def parse_tile(s):
    parts = s.lower().replace(" ", "").split("x")
    if len(parts) == 1:
        w = int(parts[0])
        return w, w
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise SystemExit(f"bad --tile {s!r} (want W or WxH)")


def check_map(m):
    if m.get("infinite"):
        raise SystemExit("infinite maps are not supported")
    ori = (m.get("orientation") or "orthogonal").lower()
    if ori != "orthogonal":
        raise SystemExit(f"{ori} maps are not supported (orthogonal only)")


def scale_num(v, f):
    if v is None or v == "":
        return v
    x = float(v) * f
    if abs(x - round(x)) < 1e-9:
        return int(round(x))
    return x


def scale_object(o, sx, sy):
    o = dict(o)
    if "x" in o: o["x"] = scale_num(o["x"], sx)
    if "y" in o: o["y"] = scale_num(o["y"], sy)
    if "width" in o: o["width"] = scale_num(o["width"], sx)
    if "height" in o: o["height"] = scale_num(o["height"], sy)
    for key in ("polygon", "polyline"):
        if key in o:
            o[key] = [{"x": scale_num(p.get("x", 0), sx), "y": scale_num(p.get("y", 0), sy)}
                      for p in (o[key] or [])]
    return o


def scale_layers(layers, sx, sy):
    out = []
    for l in layers or []:
        l = dict(l)
        if "offsetx" in l: l["offsetx"] = scale_num(l["offsetx"], sx)
        if "offsety" in l: l["offsety"] = scale_num(l["offsety"], sy)
        if l.get("type") == "group":
            l["layers"] = scale_layers(l.get("layers") or [], sx, sy)
        elif l.get("type") == "objectgroup" or "objects" in l:
            l["objects"] = [scale_object(o, sx, sy) for o in (l.get("objects") or [])]
        elif l.get("type") == "imagelayer":
            if "x" in l: l["x"] = scale_num(l["x"], sx)
            if "y" in l: l["y"] = scale_num(l["y"], sy)
        out.append(l)
    return out


def scale_map(m, new_tw, new_th):
    m = json.loads(json.dumps(m))
    check_map(m)
    tw, th = int(m.get("tilewidth") or 0), int(m.get("tileheight") or 0)
    if tw <= 0 or th <= 0:
        raise SystemExit("map has no tilewidth/tileheight")
    sx, sy = new_tw / tw, new_th / th
    m["tilewidth"], m["tileheight"] = int(new_tw), int(new_th)
    m["layers"] = scale_layers(m.get("layers") or [], sx, sy)
    return m, sx, sy


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scale a Tiled orthogonal map's tile size and object coordinates.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--factor", type=float, help="multiply tile size (and object pixels) by this")
    ap.add_argument("--tile", help="new tile size W or WxH")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if (a.factor is None) == (a.tile is None):
        sys.exit("pass exactly one of --factor or --tile")
    if a.factor is not None and a.factor <= 0:
        sys.exit("--factor must be positive")
    sources = [a.map]
    safe_out.check_any(sources, a.out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    if raw.get("type") and raw.get("type") != "map":
        sys.exit(f"{a.map} does not look like a Tiled map")
    tw, th = int(raw.get("tilewidth") or 0), int(raw.get("tileheight") or 0)
    if a.tile:
        ntw, nth = parse_tile(a.tile)
    else:
        ntw, nth = tw * a.factor, th * a.factor
        if abs(ntw - round(ntw)) < 1e-9: ntw = int(round(ntw))
        if abs(nth - round(nth)) < 1e-9: nth = int(round(nth))
    if ntw <= 0 or nth <= 0:
        sys.exit("new tile size must be positive")
    m, sx, sy = scale_map(raw, ntw, nth)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"tilewidth": m["tilewidth"], "tileheight": m["tileheight"],
           "scale_x": sx, "scale_y": sy, "out": a.out}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"tile {tw}x{th} -> {m['tilewidth']}x{m['tileheight']} (x{sx:g}, y{sy:g}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
