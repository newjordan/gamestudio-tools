#!/usr/bin/env python3
"""map-pad: grow a finite orthogonal Tiled JSON map with empty border tiles.
`--margin N` pads every side, or `--pad LEFT,TOP,RIGHT,BOTTOM` sets each side
in tiles. Objects and image layers are shifted by the left/top padding in
pixels. The inverse of map-crop (without a used-tile shrink). Encoded layers
are decoded first. The input is never overwritten unless `--in-place`.
"""
import argparse, os, copy, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def parse_pad(margin, pad):
    if (margin is None) == (pad is None):
        raise SystemExit("pass exactly one of --margin or --pad")
    if margin is not None:
        if margin < 0:
            raise SystemExit("--margin must be >= 0")
        return margin, margin, margin, margin
    parts = [int(x) for x in pad.replace("x", ",").split(",")]
    if len(parts) == 1:
        n = parts[0]
        return n, n, n, n
    if len(parts) != 4:
        raise SystemExit("--pad must be N or LEFT,TOP,RIGHT,BOTTOM")
    if any(p < 0 for p in parts):
        raise SystemExit("--pad values must be >= 0")
    return parts[0], parts[1], parts[2], parts[3]


def pad_data(data, w, h, left, top, right, bottom):
    nw, nh = w + left + right, h + top + bottom
    out = [0] * (nw * nh)
    for y in range(h):
        for x in range(w):
            g = int(data[y * w + x]) if y * w + x < len(data) else 0
            out[(y + top) * nw + (x + left)] = g
    return out, nw, nh


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pad a Tiled map with empty border tiles.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--margin", type=int, help="tiles of empty padding on every side")
    g.add_argument("--pad", help="LEFT,TOP,RIGHT,BOTTOM in tiles (or a single N)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    left, top, right, bottom = parse_pad(a.margin, a.pad)
    raw = json.load(open(a.map, encoding="utf-8"))
    if (raw.get("orientation") or "orthogonal").lower() != "orthogonal":
        sys.exit("only orthogonal maps are supported")
    if raw.get("infinite"):
        sys.exit("infinite maps are refused; run tmx-infinite-to-finite first")
    m = map_diff.decode_map(copy.deepcopy(raw))
    w, h = int(m["width"]), int(m["height"])
    tw, th = int(m.get("tilewidth") or 16), int(m.get("tileheight") or 16)
    ox, oy = left * tw, top * th
    nw, nh = w + left + right, h + top + bottom

    def walk(layers):
        for l in layers or []:
            typ = l.get("type")
            if typ == "group":
                walk(l.get("layers") or [])
            elif typ == "tilelayer":
                if l.get("chunks"):
                    sys.exit("infinite (chunked) layers are refused; run tmx-infinite-to-finite first")
                lw, lh = int(l.get("width") or w), int(l.get("height") or h)
                data, lw2, lh2 = pad_data(l.get("data") or [], lw, lh, left, top, right, bottom)
                l["data"] = data
                l["width"], l["height"] = lw2, lh2
                l["x"] = 0
                l["y"] = 0
                l.pop("encoding", None)
                l.pop("compression", None)
            elif typ == "objectgroup":
                for o in l.get("objects") or []:
                    o["x"] = float(o.get("x") or 0) + ox
                    o["y"] = float(o.get("y") or 0) + oy
            elif typ == "imagelayer":
                l["x"] = float(l.get("x") or 0) + ox
                l["y"] = float(l.get("y") or 0) + oy
    walk(m.get("layers") or [])
    m["width"], m["height"] = nw, nh
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"out": a.out, "pad": [left, top, right, bottom], "in_size": [w, h], "out_size": [nw, nh]}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{w}x{h} -> {nw}x{nh} (pad {left},{top},{right},{bottom}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
