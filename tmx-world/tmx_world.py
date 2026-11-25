#!/usr/bin/env python3
"""tmx-world: build a Tiled `.world` index from a folder of finite maps (or an
explicit list). Placement is taken from each map's `chunk_x` / `chunk_y`
properties when `--from-props` (the default after map-chunk), from a
`..._X_Y` filename when `--from-filename`, or laid out in a left-to-right grid
with `--layout grid --columns N`. Pixel sizes come from each map's tile size.
The world file is never an in-place overwrite of a source map unless `--in-place`.
"""
import argparse, os, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

NAME_RE = re.compile(r"(?:^|[_-])(-?\d+)[_-](-?\d+)\.(?:json|tmj|tmx)$", re.I)


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith((".json", ".tmj", ".tmx")) and not f.lower().endswith(".world"):
                    out.append(os.path.join(p, f))
        elif os.path.isfile(p):
            out.append(p)
        else:
            raise SystemExit(f"not a file or folder: {p}")
    # drop the destination if a user passed a .world by mistake
    out = [p for p in out if not p.lower().endswith(".world")]
    if not out:
        raise SystemExit("no maps found")
    return list(dict.fromkeys(out))


def prop(m, name):
    for p in m.get("properties") or []:
        if p.get("name") == name:
            return p.get("value")
    return None


def load_map(path):
    if path.lower().endswith((".tmx", ".xml")):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmx-to-json"))
        import tmx_to_json
        return tmx_to_json.convert(path)
    return json.load(open(path, encoding="utf-8"))


def place(path, m, mode):
    tw, th = int(m.get("tilewidth") or 16), int(m.get("tileheight") or 16)
    w, h = int(m.get("width") or 0), int(m.get("height") or 0)
    px, py = None, None
    if mode in ("props", "auto"):
        cx, cy = prop(m, "chunk_x"), prop(m, "chunk_y")
        if cx is not None and cy is not None:
            px, py = int(cx) * tw, int(cy) * th
    if px is None and mode in ("filename", "auto"):
        mo = NAME_RE.search(os.path.basename(path))
        if mo:
            px, py = int(mo.group(1)) * tw, int(mo.group(2)) * th
    return px, py, w * tw, h * th


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Tiled .world index from a folder of maps.")
    ap.add_argument("inputs", nargs="+", help="map files or a folder")
    ap.add_argument("-o", "--out", required=True, help="output .world path")
    ap.add_argument("--from-props", action="store_true", help="place by chunk_x / chunk_y (default if present)")
    ap.add_argument("--from-filename", action="store_true", help="place by a trailing _X_Y in the filename (tile coords)")
    ap.add_argument("--layout", choices=("auto", "grid"), default="auto")
    ap.add_argument("--columns", type=int, default=0, help="columns for --layout grid (0 = square-ish)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if sum(bool(x) for x in (a.from_props, a.from_filename, a.layout == "grid")) > 1 and a.layout == "grid":
        # grid wins over filename/props when explicitly requested; flags still ok together if layout stays auto
        pass
    paths = collect(a.inputs)
    for p in paths:
        safe_out.check(p, a.out, a.in_place)
    if a.json:
        for p in paths:
            safe_out.check(p, a.json, a.in_place)
    mode = "grid" if a.layout == "grid" else ("props" if a.from_props else ("filename" if a.from_filename else "auto"))
    loaded = [(p, load_map(p)) for p in paths]
    maps = []
    world_dir = os.path.dirname(os.path.abspath(a.out)) or "."
    if mode == "grid":
        cols = a.columns or int(max(1, np_ceil_sqrt(len(loaded))))
        cursor_x = cursor_y = 0
        row_h = 0
        col = 0
        max_w = max(int(m.get("width") or 0) * int(m.get("tilewidth") or 16) for _, m in loaded) or 1
        for p, m in loaded:
            tw, th = int(m.get("tilewidth") or 16), int(m.get("tileheight") or 16)
            w, h = int(m.get("width") or 0) * tw, int(m.get("height") or 0) * th
            maps.append({"fileName": os.path.relpath(os.path.abspath(p), world_dir),
                         "x": cursor_x, "y": cursor_y, "width": w, "height": h})
            row_h = max(row_h, h)
            col += 1
            if col >= cols:
                cursor_x, cursor_y, col, row_h = 0, cursor_y + row_h, 0, 0
            else:
                cursor_x += w if w else max_w
    else:
        missing = []
        for p, m in loaded:
            px, py, w, h = place(p, m, mode)
            if px is None:
                missing.append(p)
                continue
            maps.append({"fileName": os.path.relpath(os.path.abspath(p), world_dir),
                         "x": px, "y": py, "width": w, "height": h})
        if missing:
            sys.exit("could not place " + ", ".join(missing)
                     + " (no chunk_x/chunk_y and no _X_Y filename; use --layout grid)")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump({"type": "world", "maps": maps}, open(a.out, "w"), indent=2)
    rec = {"out": a.out, "maps": len(maps), "mode": mode}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(maps)} map(s) indexed -> {a.out}")
    return 0


def np_ceil_sqrt(n):
    import math
    return int(math.ceil(n ** 0.5))


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
