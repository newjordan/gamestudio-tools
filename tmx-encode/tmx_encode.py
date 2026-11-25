#!/usr/bin/env python3
"""tmx-encode: re-encode Tiled tile data as csv, a plain JSON array, or base64 with
zlib / gzip / (when available) zstd — the inverse of the kit's decoders. Accepts a
Tiled JSON map (`.json` / `.tmj`) or a TMX (`.tmx` / `.xml`). All tile layers and
infinite-map chunks are rewritten. zstd is offered only when `compression.zstd`
(Python 3.14+), `pyzstd`, or `zstd` can compress. The input is never overwritten
unless `--in-place`.
"""
import argparse, os, base64, gzip, json, struct, sys, zlib
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402


def zstd_compress(raw, layer_name=""):
    for mod, attr in (("compression.zstd", "compress"), ("pyzstd", "compress"), ("zstd", "compress")):
        try:
            parts = mod.split(".")
            m = __import__(mod, fromlist=[parts[-1]] if len(parts) > 1 else [])
            return getattr(m, attr)(raw)
        except ImportError:
            continue
        except Exception as e:
            raise SystemExit(f"layer {layer_name!r}: zstd compress failed ({e})")
    raise SystemExit(
        f"layer {layer_name!r}: zstd-compressed tile data needs Python 3.14+ compression.zstd, pyzstd, or zstd; "
        "none are available here. Export as zlib, gzip, csv, or a plain array."
    )


def encode_gids(gids, encoding, compression, width=None, layer_name=""):
    gids = [int(g) for g in gids]
    if encoding == "array":
        if compression and compression != "none":
            raise SystemExit("a plain JSON array cannot be compressed; use --encoding base64")
        return gids, None, None
    if encoding == "csv":
        if compression and compression != "none":
            raise SystemExit("csv tile data cannot be compressed; use --encoding base64")
        if width and width > 0:
            rows = []
            for i in range(0, len(gids), width):
                rows.append(",".join(str(g) for g in gids[i:i + width]) + ",")
            text = "\n".join(rows)
        else:
            text = ",".join(str(g) for g in gids)
        return text, "csv", None
    if encoding != "base64":
        raise SystemExit(f"unsupported encoding {encoding!r}")
    raw = struct.pack(f"<{len(gids)}I", *gids) if gids else b""
    comp = compression or "none"
    if comp in ("none", "", None):
        payload, ckey = raw, None
    elif comp in ("zlib", "zip"):
        payload, ckey = zlib.compress(raw), "zlib"
    elif comp in ("gzip", "gz"):
        payload, ckey = gzip.compress(raw), "gzip"
    elif comp in ("zstd", "zstandard"):
        payload, ckey = zstd_compress(raw, layer_name), "zstd"
    else:
        raise SystemExit(f"unsupported compression {compression!r}")
    return base64.b64encode(payload).decode("ascii"), "base64", ckey


def encode_layers(layers, encoding, compression):
    n = 0
    for l in layers or []:
        if l.get("type") == "group":
            n += encode_layers(l.get("layers") or [], encoding, compression)
        elif l.get("type") == "tilelayer":
            w = int(l.get("width") or 0)
            if "chunks" in l:
                for c in l["chunks"]:
                    gids = c.get("data") or []
                    cw = int(c.get("width") or w or 0)
                    data, enc, comp = encode_gids(gids, encoding, compression, cw, l.get("name"))
                    c["data"] = data
                    if enc:
                        # encoding/compression live on the layer in Tiled JSON
                        pass
                if encoding == "array":
                    l.pop("encoding", None)
                    l.pop("compression", None)
                else:
                    l["encoding"] = enc if encoding != "array" else None
                    if encoding == "base64" and compression not in ("none", "", None):
                        _, _, ckey = encode_gids([0], encoding, compression, 1, l.get("name"))
                        # set from last chunk encode
                    # use last encoded keys
                    if l["chunks"]:
                        # re-read from a dummy? we already have enc/comp from last chunk
                        l["encoding"] = enc
                        if comp:
                            l["compression"] = comp
                        else:
                            l.pop("compression", None)
                    n += len(l["chunks"])
            elif "data" in l:
                data, enc, comp = encode_gids(l.get("data") or [], encoding, compression, w, l.get("name"))
                l["data"] = data
                if encoding == "array":
                    l.pop("encoding", None)
                    l.pop("compression", None)
                else:
                    l["encoding"] = enc
                    if comp:
                        l["compression"] = comp
                    else:
                        l.pop("compression", None)
                n += 1
    return n


def encode_json_map(raw, encoding, compression):
    m = map_diff.decode_map(raw)
    n = encode_layers(m.get("layers") or [], encoding, compression)
    return m, n


def _local(tag):
    return tag.split("}", 1)[-1]


def encode_tmx(tree, encoding, compression):
    if encoding == "array":
        raise SystemExit("TMX cannot store a plain JSON array; use csv or base64")
    n = 0
    for data in tree.getroot().iter():
        if _local(data.tag) != "data":
            continue
        layer = None
        # width: parent layer or chunk
        parent = None
        # ElementTree has no getparent in stdlib; look at attrib and infer from text
        # We'll decode from this element's own encoding/compression, then rewrite.
        enc = data.get("encoding") or "csv"
        comp = data.get("compression")
        text = (data.text or "").strip()
        # child <tile gid="..."/> form
        if not text and list(data):
            gids = [int(c.get("gid") or 0) for c in data if _local(c.tag) == "tile"]
            for c in list(data):
                data.remove(c)
        else:
            gids = map_diff.decode_tile_data(text, enc, comp, "tmx")
        # width from ancestor? not available; encode as one row if csv without width
        width = None
        payload, enc2, comp2 = encode_gids(gids, encoding, compression, width, "tmx")
        data.text = "\n" + payload + "\n" if encoding == "csv" else payload
        data.set("encoding", enc2)
        if comp2:
            data.set("compression", comp2)
        elif "compression" in data.attrib:
            del data.attrib["compression"]
        n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description="Re-encode Tiled tile data as csv, a JSON array, or base64 zlib/gzip/zstd.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--encoding", choices=("csv", "base64", "array"), default="base64")
    ap.add_argument("--compression", choices=("none", "zlib", "gzip", "zstd"), default="zlib",
                    help="used with --encoding base64 (default: zlib). Ignored for csv/array.")
    ap.add_argument("--json", help="report path")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.encoding in ("csv", "array") and a.compression not in ("none", "zlib"):
        # default compression is zlib; silently treat as none for csv/array unless user set it
        if "--compression" in (argv or sys.argv):
            sys.exit(f"--encoding {a.encoding} cannot be combined with --compression {a.compression}")
        a.compression = "none"
    elif a.encoding in ("csv", "array"):
        a.compression = "none"
    sources = [a.map]
    safe_out.check_any(sources, a.out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    low = a.map.lower()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    if low.endswith((".tmx", ".xml")):
        tree = ET.parse(a.map)
        n = encode_tmx(tree, a.encoding, a.compression)
        tree.write(a.out, encoding="utf-8", xml_declaration=True)
    else:
        raw = json.load(open(a.map, encoding="utf-8"))
        m, n = encode_json_map(raw, a.encoding, a.compression)
        json.dump(m, open(a.out, "w"), indent=2)
    rec = {"layers_or_chunks": n, "encoding": a.encoding,
           "compression": None if a.compression == "none" else a.compression, "out": a.out}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=2)
    extra = f"+{a.compression}" if a.encoding == "base64" and a.compression != "none" else ""
    print(f"{n} layer(s)/chunk(s) encoded as {a.encoding}{extra} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
