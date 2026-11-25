#!/usr/bin/env python3
"""map-blank: write an empty finite orthogonal Tiled JSON map of a given size.
`--size WxH` is the map in tiles; `--tile N` or `--tile WxH` is the tile size
(default 16). `--layers` is a comma-separated list of empty tile layer names
(default: ground). Optional `--tileset` adds a tileset reference. There is no
input file; `-o` is required.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def parse_wh(s, flag):
    parts = [int(x) for x in s.lower().replace("x", ",").split(",")]
    if len(parts) == 1:
        return parts[0], parts[0]
    if len(parts) != 2 or parts[0] <= 0 or parts[1] <= 0:
        raise SystemExit(f"{flag} must be N or WxH with positive integers")
    return parts[0], parts[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write an empty finite orthogonal Tiled JSON map.")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--size", required=True, help="map size in tiles, WxH")
    ap.add_argument("--tile", default="16", help="tile size in pixels, N or WxH (default: 16)")
    ap.add_argument("--layers", default="ground", help="comma-separated tile layer names (default: ground)")
    ap.add_argument("--tileset", help="optional tileset image or JSON path recorded as a tileset reference")
    ap.add_argument("--tileset-name", default="tiles")
    ap.add_argument("--tilecount", type=int, default=1)
    ap.add_argument("--columns", type=int, default=1)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    w, h = parse_wh(a.size, "--size")
    tw, th = parse_wh(a.tile, "--tile")
    names = [n.strip() for n in a.layers.split(",") if n.strip()]
    if not names:
        sys.exit("no layer names")
    if a.json:
        # no input to collide with, but still refuse writing json over the map if they match later
        pass
    m = {
        "type": "map",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": w,
        "height": h,
        "tilewidth": tw,
        "tileheight": th,
        "infinite": False,
        "nextlayerid": len(names) + 1,
        "nextobjectid": 1,
        "tilesets": [],
        "layers": [],
    }
    for i, name in enumerate(names, start=1):
        m["layers"].append({
            "type": "tilelayer", "id": i, "name": name, "width": w, "height": h,
            "visible": True, "opacity": 1, "x": 0, "y": 0,
            "data": [0] * (w * h),
        })
    if a.tileset:
        ts = {"name": a.tileset_name, "firstgid": 1, "tilewidth": tw, "tileheight": th,
              "tilecount": a.tilecount, "columns": a.columns,
              "image": a.tileset, "imagewidth": a.columns * tw,
              "imageheight": ((a.tilecount + a.columns - 1) // a.columns) * th}
        m["tilesets"].append(ts)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None))
    rec = {"out": a.out, "size": [w, h], "tile": [tw, th], "layers": names}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{w}x{h} map, {len(names)} layer(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
