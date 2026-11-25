#!/usr/bin/env python3
"""tmx-decode: expand encoded Tiled tile data (csv, base64 zlib/gzip/zstd, or XML
<tile> children) to a plain JSON array or to csv — the inverse of tmx-encode.
Accepts a Tiled JSON map (`.json` / `.tmj`) or a TMX (`.tmx` / `.xml`). All tile
layers and infinite-map chunks are rewritten. zstd is decoded when
`compression.zstd` (Python 3.14+), `pyzstd`, or `zstd` is importable. The input
is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmx-encode"))
import safe_out, map_diff, tmx_encode  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Decode Tiled tile data to a JSON array or csv.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--encoding", choices=("array", "csv"), default=None,
                    help="array (default for JSON) or csv (default and only option for TMX output)")
    ap.add_argument("--json", help="report path")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    sources = [a.map]
    safe_out.check_any(sources, a.out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    low_in, low_out = a.map.lower(), a.out.lower()
    tmx_in = low_in.endswith((".tmx", ".xml"))
    tmx_out = low_out.endswith((".tmx", ".xml"))
    enc = a.encoding
    if enc is None:
        enc = "csv" if tmx_out else "array"
    if tmx_out and enc == "array":
        sys.exit("TMX cannot store a plain JSON array; use --encoding csv or write a .json")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    if tmx_in and tmx_out:
        tree = ET.parse(a.map)
        n = tmx_encode.encode_tmx(tree, enc, "none")
        tree.write(a.out, encoding="utf-8", xml_declaration=True)
    else:
        if tmx_in:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmx-to-json"))
            import tmx_to_json
            raw = tmx_to_json.convert(a.map)
        else:
            raw = json.load(open(a.map, encoding="utf-8"))
        m, n = tmx_encode.encode_json_map(raw, enc, "none")
        if tmx_out:
            sys.exit("writing TMX from a JSON map is not supported; decode to .json, or pass a .tmx in")
        json.dump(m, open(a.out, "w"), indent=2)
    rec = {"layers_or_chunks": n, "encoding": enc, "out": a.out}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{n} layer(s)/chunk(s) decoded to {enc} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
