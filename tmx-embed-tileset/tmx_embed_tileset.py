#!/usr/bin/env python3
"""tmx-embed-tileset: inline external Tiled tilesets (`.tsx` / `.tsj` / `.json`) into a Tiled
JSON map so the map is self-contained. Uses the same resolver as map-diff / tile-preview
(`firstgid` from the map wins; image paths are rewritten relative to the output map). Writes a
new map; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def relativize_image(ts, out_dir):
    ts = dict(ts)
    ts.pop("source", None)
    img = ts.get("image")
    if img and os.path.isabs(img) and out_dir:
        try:
            ts["image"] = os.path.relpath(img, out_dir)
        except ValueError:
            pass
    return ts


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inline external Tiled tilesets into a JSON map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--abs-images", action="store_true",
                    help="leave tileset image paths absolute (default: relative to the output map)")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(a.map))
    n_ext = sum(1 for ts in (raw.get("tilesets") or []) if ts.get("source"))
    m = map_diff.resolve_map_tilesets(raw, base)
    out_dir = os.path.dirname(os.path.abspath(a.out)) or "."
    cleaned = []
    for ts in m.get("tilesets") or []:
        ts = dict(ts)
        ts.pop("source", None)
        if not a.abs_images:
            ts = relativize_image(ts, out_dir)
        cleaned.append(ts)
    m["tilesets"] = cleaned
    leftover = [ts.get("name") or ts.get("source") for ts in m["tilesets"] if ts.get("source")]
    if leftover:
        sys.exit("tileset still has a source after embed: " + ", ".join(map(str, leftover)))
    os.makedirs(out_dir or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"embedded": n_ext, "tilesets": len(m.get("tilesets") or []), "out": a.out}
    print(f"embedded {n_ext} external tileset(s), {rec['tilesets']} total -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
