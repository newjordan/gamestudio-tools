#!/usr/bin/env python3
"""map-shift: shift every tile and object on a finite orthogonal Tiled JSON map
by a tile offset (`--tiles DX,DY`) and/or a pixel offset (`--pixels DX,DY`).
Tiles that leave the map are dropped (vacated cells become 0) unless `--wrap`
rolls them around. Objects are moved by the combined pixel delta and dropped
when `--clip-objects` and their bbox leaves the map. Encoded layers are decoded
first. The input is never overwritten unless `--in-place`.
"""
import argparse, os, copy, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-chunk"))
import safe_out, map_diff, map_chunk  # noqa: E402


def parse_pair(s, name):
    if s is None:
        return 0, 0
    raw = s.replace(" ", "")
    for sep in (",", "x", ":"):
        if sep in raw:
            a, b = raw.split(sep, 1)
            return int(a), int(b)
    raise SystemExit(f"{name} must be DX,DY (or DxDY)")


def shift_tiles(data, w, h, dx, dy, wrap):
    out = [0] * (w * h)
    moved = 0
    for y in range(h):
        for x in range(w):
            g = int(data[y * w + x]) if y * w + x < len(data) else 0
            if not g:
                continue
            nx, ny = x + dx, y + dy
            if wrap:
                nx %= w
                ny %= h
            elif not (0 <= nx < w and 0 <= ny < h):
                continue
            out[ny * w + nx] = g
            moved += 1
    return out, moved


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shift tiles and objects on a Tiled map by a tile and/or pixel offset.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tiles", default="0,0", help="tile offset DX,DY (default 0,0)")
    ap.add_argument("--pixels", default="0,0", help="extra pixel offset DX,DY applied to objects (and added to tile offset * tile size)")
    ap.add_argument("--wrap", action="store_true", help="wrap tiles around the map instead of dropping them")
    ap.add_argument("--clip-objects", action="store_true", help="drop objects whose bbox leaves the map")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    tdx, tdy = parse_pair(a.tiles, "--tiles")
    pdx, pdy = parse_pair(a.pixels, "--pixels")
    raw = json.load(open(a.map, encoding="utf-8"))
    if (raw.get("orientation") or "orthogonal").lower() != "orthogonal":
        sys.exit("only orthogonal maps are supported")
    if raw.get("infinite"):
        sys.exit("infinite maps are refused; run tmx-infinite-to-finite first")
    m = map_diff.decode_map(copy.deepcopy(raw))
    w, h = int(m["width"]), int(m["height"])
    tw, th = int(m.get("tilewidth") or 16), int(m.get("tileheight") or 16)
    ox, oy = tdx * tw + pdx, tdy * th + pdy
    tiles_moved = objs_moved = objs_dropped = 0

    def walk(layers):
        nonlocal tiles_moved, objs_moved, objs_dropped
        for l in layers or []:
            typ = l.get("type")
            if typ == "group":
                walk(l.get("layers") or [])
            elif typ == "tilelayer":
                if l.get("chunks"):
                    sys.exit("infinite (chunked) layers are refused; run tmx-infinite-to-finite first")
                lw = int(l.get("width") or w)
                lh = int(l.get("height") or h)
                data, n = shift_tiles(l.get("data") or [], lw, lh, tdx, tdy, a.wrap)
                l["data"] = data
                l.pop("encoding", None)
                l.pop("compression", None)
                tiles_moved += n
            elif typ == "objectgroup":
                kept = []
                for o in l.get("objects") or []:
                    no = copy.deepcopy(o)
                    no["x"] = float(o.get("x") or 0) + ox
                    no["y"] = float(o.get("y") or 0) + oy
                    if a.clip_objects:
                        x0, y0, x1, y1 = map_chunk.obj_bbox(no)
                        if x1 <= 0 or y1 <= 0 or x0 >= w * tw or y0 >= h * th:
                            objs_dropped += 1
                            continue
                    kept.append(no)
                    objs_moved += 1
                l["objects"] = kept
            elif typ == "imagelayer":
                l["x"] = float(l.get("x") or 0) + ox
                l["y"] = float(l.get("y") or 0) + oy
    walk(m.get("layers") or [])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"out": a.out, "tiles": [tdx, tdy], "pixels": [pdx, pdy], "delta_px": [ox, oy],
           "tiles_moved": tiles_moved, "objects_moved": objs_moved, "objects_dropped": objs_dropped,
           "wrap": a.wrap}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{tiles_moved} tile(s), {objs_moved} object(s) shifted ({objs_dropped} clipped) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
