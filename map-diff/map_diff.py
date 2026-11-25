#!/usr/bin/env python3
"""map-diff: review diff of two Tiled JSON maps, for level changes in code review. Reports map settings and tileset changes,
layers added / removed / reordered (matched by name), per tile layer the number of changed cells with their bounding box and
the most common tile swaps, and per object layer the objects added, removed, moved (matched by id) or edited, plus layer and
map custom property changes. Text, Markdown (--md) and JSON (--json) output; --fail-on-diff gives a CI exit code.
Finite and infinite maps are compared cell by cell (flip flags are part of the tile, so a flip counts as a change). Encoded (base64 zlib/gzip or csv) tile data is decoded first; zstd is decoded with a native decoder when one is importable, otherwise with the kit's own pure-Python decoder (lib/zstd_pure.py).
"""
import argparse, os, base64, gzip, json, struct, sys, zlib
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import zstd_pure  # noqa: E402


def flat_layers(layers, prefix=""):
    for l in layers:
        name = prefix + l.get("name", "")
        if l.get("type") == "group": yield from flat_layers(l.get("layers", []), name + "/")
        else: yield name, l



def zstd_decompress(raw, layer_name=""):
    """Decompress zstd bytes: a native decoder when one is importable (Python 3.14 compression.zstd, pyzstd, zstd),
    otherwise the kit's pure-Python decoder (lib/zstd_pure.py: raw, RLE and compressed blocks, no dictionaries)."""
    try:
        return zstd_pure.decompress_auto(raw)
    except GstInputError as e:
        raise GstInputError(f"layer {layer_name!r}: {e}") from e


def decode_tile_data(data, encoding=None, compression=None, layer_name=""):
    """Plain GID list from a Tiled layer or chunk `data` field (array, csv string, or base64 with zlib/gzip).
    zstd is decoded natively when importable, otherwise by lib/zstd_pure.py (no dictionaries).
    Malformed base64 or a length that is not a multiple of 4 exits."""
    if data is None: return []
    if isinstance(data, list): return list(data)
    if not isinstance(data, str):
        raise GstInputError(f"layer {layer_name!r}: unexpected tile data type {type(data).__name__}")
    enc = (encoding or "base64").lower()
    if enc == "csv":
        return [int(x) for x in data.replace("\n", "").split(",") if x.strip()]
    if enc != "base64":
        raise GstInputError(f"layer {layer_name!r}: unsupported encoding {encoding!r}")
    try:
        raw = base64.b64decode(data.strip(), validate=False)
    except Exception as e:
        raise GstInputError(f"layer {layer_name!r}: invalid base64 ({e})")
    comp = (compression or "").lower()
    if comp in ("zlib", "zip"):
        try:
            raw = zlib.decompress(raw)
        except zlib.error as e:
            raise GstInputError(f"layer {layer_name!r}: zlib data is corrupt ({e})") from e
    elif comp in ("gzip", "gz"):
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError, zlib.error) as e:
            raise GstInputError(f"layer {layer_name!r}: gzip data is corrupt ({e})") from e
    elif comp in ("zstd", "zstandard"):
        raw = zstd_decompress(raw, layer_name)
    elif comp:
        raise GstInputError(f"layer {layer_name!r}: unsupported compression {compression!r}")
    if len(raw) % 4:
        raise GstInputError(f"layer {layer_name!r}: decoded tile data length {len(raw)} is not a multiple of 4")
    return list(struct.unpack(f"<{len(raw) // 4}I", raw))


def layer_gids(l, chunk=None):
    src = chunk if chunk is not None else l
    return decode_tile_data(src.get("data", []), l.get("encoding") or (chunk or {}).get("encoding"),
                            l.get("compression") or (chunk or {}).get("compression"), l.get("name"))


def decode_map(m):
    """Return a deep copy whose tile-layer (and chunk) data strings are expanded to GID arrays; encoding keys are dropped."""
    if not isinstance(m, dict):
        raise GstInputError("Tiled map document is not an object")
    m = json.loads(json.dumps(m))
    def walk(layers):
        for l in layers or []:
            if not isinstance(l, dict):
                raise GstInputError("Tiled layer is not an object")
            if l.get("type") == "group": walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                name = l.get("name") or ""
                if "chunks" in l:
                    if not isinstance(l["chunks"], list):
                        raise GstInputError("Tiled layer %r chunks are not a list" % name)
                    for c in l["chunks"]:
                        if not isinstance(c, dict):
                            raise GstInputError("Tiled layer %r chunk is not an object" % name)
                        gids = layer_gids(l, c)
                        gst_read.check_tiled_layer_length(gids, c.get("width"), c.get("height"), name)
                        c["data"] = gids
                        c.pop("encoding", None); c.pop("compression", None)
                elif "data" in l or l.get("encoding"):
                    gids = layer_gids(l)
                    gst_read.check_tiled_layer_length(gids, l.get("width"), l.get("height"), name)
                    l["data"] = gids
                l.pop("encoding", None); l.pop("compression", None)
    walk(m.get("layers") or []); return m


def load_tsx(path):
    """Tiled TSX (XML tileset) -> a JSON-style tileset dict (image, tiles, animation frames)."""
    root = gst_read.parse_xml(path, "Tiled tileset").getroot()
    if root.tag != "tileset": raise GstInputError(f"not a Tiled tileset: {path}")
    def _int(el, k, default=0):
        v = el.get(k); return default if v is None else int(v)
    t = {"name": root.get("name") or os.path.splitext(os.path.basename(path))[0],
         "tilewidth": _int(root, "tilewidth"), "tileheight": _int(root, "tileheight"),
         "tilecount": _int(root, "tilecount"), "columns": _int(root, "columns"),
         "margin": _int(root, "margin"), "spacing": _int(root, "spacing")}
    if root.get("objectalignment"): t["objectalignment"] = root.get("objectalignment")
    im = root.find("image")
    if im is not None:
        t["image"] = im.get("source") or ""
        if im.get("width"): t["imagewidth"] = int(im.get("width"))
        if im.get("height"): t["imageheight"] = int(im.get("height"))
    off = root.find("tileoffset")
    if off is not None:
        t["tileoffset"] = {"x": _int(off, "x"), "y": _int(off, "y")}
    tiles = []
    for tile in root.findall("tile"):
        rec = {"id": int(tile.get("id", 0))}
        timg = tile.find("image")                      # image-collection tilesets: one image per tile
        if timg is not None and timg.get("source"):
            rec["image"] = timg.get("source")
            if timg.get("width"): rec["imagewidth"] = int(timg.get("width"))
            if timg.get("height"): rec["imageheight"] = int(timg.get("height"))
        anim = tile.find("animation")
        if anim is not None:
            rec["animation"] = [{"tileid": int(f.get("tileid", 0)), "duration": int(f.get("duration", 0))} for f in anim.findall("frame")]
        typ = tile.get("type") or tile.get("class")
        if typ: rec["type"] = typ
        tiles.append(rec)
    if tiles: t["tiles"] = tiles
    return t


def resolve_tileset(ts, base):
    """If the tileset has a `source` (.tsx / .tsj / .json), load it and merge (map firstgid wins).
    Image paths inside the external file are resolved next to that file and stored as an absolute path."""
    src = ts.get("source")
    if not src: return dict(ts)
    path = src if os.path.isabs(src) else os.path.join(base, src)
    if not os.path.isfile(path): raise GstInputError(f"external tileset not found: {path}")
    low = path.lower()
    if low.endswith((".tsx", ".xml")):
        try: ext = load_tsx(path)
        except (ValueError, TypeError) as e: raise GstInputError(f"external tileset {path} has a bad number: {e}") from e
    else:
        ext = json.load(open(path))
        if ext.get("type") == "map": raise GstInputError(f"external tileset {path} looks like a map, not a tileset")
    merged = dict(ext)
    for k, v in ts.items():
        if k != "source": merged[k] = v
    if merged.get("image") and not os.path.isabs(merged["image"]):
        merged["image"] = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), merged["image"]))
    merged["firstgid"] = ts.get("firstgid", ext.get("firstgid", 1))
    if isinstance(merged.get("tiles"), list):          # per-tile images are relative to the external file too
        here = os.path.dirname(os.path.abspath(path))
        fixed = []
        for tile in merged["tiles"]:
            if isinstance(tile, dict) and tile.get("image") and not os.path.isabs(str(tile["image"])):
                tile = dict(tile, image=os.path.normpath(os.path.join(here, str(tile["image"]))))
            fixed.append(tile)
        merged["tiles"] = fixed
    return merged


def resolve_map_tilesets(m, base):
    m = json.loads(json.dumps(m))
    m["tilesets"] = [resolve_tileset(ts, base) for ts in (m.get("tilesets") or [])]
    return m


def cells(l):
    """-> dict {(x, y): gid} of non-empty cells."""
    out = {}
    if "chunks" in l:
        for c in l["chunks"]:
            for i, g in enumerate(layer_gids(l, c)):
                if g: out[(c["x"] + i % c["width"], c["y"] + i // c["width"])] = g
    else:
        w = l.get("width", 0); d = layer_gids(l)
        for i, g in enumerate(d):
            if g: out[(l.get("startx", 0) + i % w, l.get("starty", 0) + i // w)] = g
    return out


def props(o):
    p = o.get("properties") or []
    if isinstance(p, dict): return dict(p)
    return {q["name"]: q.get("value") for q in p}


def propdiff(a, b):
    pa, pb = props(a), props(b); d = {}
    for k in sorted(pa.keys() | pb.keys()):
        if pa.get(k, None) != pb.get(k, None) or (k in pa) != (k in pb): d[k] = [pa.get(k), pb.get(k)]
    return d


def diff_tiles(la, lb):
    A, B = cells(la), cells(lb); keys = A.keys() | B.keys(); ch = [(k, A.get(k, 0), B.get(k, 0)) for k in keys if A.get(k, 0) != B.get(k, 0)]
    if not ch: return None
    xs = [k[0] for k, _, _ in ch]; ys = [k[1] for k, _, _ in ch]
    swaps = Counter((a, b) for _, a, b in ch).most_common(5)
    return {"changed": len(ch), "added": sum(1 for _, a, b in ch if not a), "cleared": sum(1 for _, a, b in ch if not b),
            "bbox": [min(xs), min(ys), max(xs), max(ys)], "top_swaps": [[a, b, n] for (a, b), n in swaps]}


OBJ_FIELDS = ("name", "type", "class", "x", "y", "width", "height", "rotation", "gid", "visible", "point", "ellipse")


def diff_objects(la, lb):
    A = {o["id"]: o for o in la.get("objects", [])}; B = {o["id"]: o for o in lb.get("objects", [])}
    res = {"added": [], "removed": [], "moved": [], "edited": []}
    for i in sorted(B.keys() - A.keys()): res["added"].append({"id": i, "name": B[i].get("name", ""), "type": B[i].get("type") or B[i].get("class", ""), "x": B[i].get("x"), "y": B[i].get("y")})
    for i in sorted(A.keys() - B.keys()): res["removed"].append({"id": i, "name": A[i].get("name", ""), "type": A[i].get("type") or A[i].get("class", "")})
    for i in sorted(A.keys() & B.keys()):
        a, b = A[i], B[i]
        if (a.get("x"), a.get("y")) != (b.get("x"), b.get("y")): res["moved"].append({"id": i, "name": b.get("name", ""), "from": [a.get("x"), a.get("y")], "to": [b.get("x"), b.get("y")]})
        ed = {f: [a.get(f), b.get(f)] for f in OBJ_FIELDS if f not in ("x", "y") and a.get(f) != b.get(f)}
        pd = propdiff(a, b)
        if pd: ed["properties"] = pd
        if ed: res["edited"].append({"id": i, "name": b.get("name", ""), "changes": ed})
    return res if any(res.values()) else None


def diff(a, b):
    a, b = decode_map(a), decode_map(b)
    d = {"map": {}, "tilesets": {"added": [], "removed": [], "changed": []}, "layers": {"added": [], "removed": [], "order_changed": False, "changed": {}}}
    for k in ("width", "height", "tilewidth", "tileheight", "orientation", "infinite", "renderorder"):
        if a.get(k) != b.get(k): d["map"][k] = [a.get(k), b.get(k)]
    pd = propdiff(a, b)
    if pd: d["map"]["properties"] = pd
    ta = {(t.get("name") or t.get("source")): t for t in a.get("tilesets", [])}; tb = {(t.get("name") or t.get("source")): t for t in b.get("tilesets", [])}
    d["tilesets"]["added"] = sorted(tb.keys() - ta.keys()); d["tilesets"]["removed"] = sorted(ta.keys() - tb.keys())
    for k in sorted(ta.keys() & tb.keys()):
        ch = {f: [ta[k].get(f), tb[k].get(f)] for f in ("firstgid", "image", "tilecount", "columns") if ta[k].get(f) != tb[k].get(f)}
        if ch: d["tilesets"]["changed"].append({"name": k, "changes": ch})
    LA, LB = dict(flat_layers(a.get("layers", []))), dict(flat_layers(b.get("layers", [])))
    d["layers"]["added"] = [n for n in LB if n not in LA]; d["layers"]["removed"] = [n for n in LA if n not in LB]
    common_a = [n for n in LA if n in LB]; common_b = [n for n in LB if n in LA]; d["layers"]["order_changed"] = common_a != common_b
    for n in common_a:
        la, lb = LA[n], LB[n]; ch = {}
        if la.get("type") != lb.get("type"): ch["type"] = [la.get("type"), lb.get("type")]
        elif la.get("type") == "tilelayer":
            t = diff_tiles(la, lb)
            if t: ch["tiles"] = t
        elif la.get("type") == "objectgroup":
            o = diff_objects(la, lb)
            if o: ch["objects"] = o
        for f in ("visible", "opacity", "offsetx", "offsety"):
            if la.get(f) != lb.get(f): ch[f] = [la.get(f), lb.get(f)]
        pd = propdiff(la, lb)
        if pd: ch["properties"] = pd
        if ch: d["layers"]["changed"][n] = ch
    d["has_changes"] = bool(d["map"] or any(d["tilesets"].values()) or d["layers"]["added"] or d["layers"]["removed"] or d["layers"]["order_changed"] or d["layers"]["changed"])
    return d


def lines(d):
    L = []
    for k, v in d["map"].items(): L.append(f"map {k}: {v[0]} -> {v[1]}" if k != "properties" else "map properties: " + "; ".join(f"{p}: {x[0]!r} -> {x[1]!r}" for p, x in v.items()))
    for t in d["tilesets"]["added"]: L.append(f"+ tileset {t}")
    for t in d["tilesets"]["removed"]: L.append(f"- tileset {t}")
    for t in d["tilesets"]["changed"]: L.append(f"~ tileset {t['name']}: " + "; ".join(f"{f} {x[0]} -> {x[1]}" for f, x in t["changes"].items()))
    for n in d["layers"]["added"]: L.append(f"+ layer {n}")
    for n in d["layers"]["removed"]: L.append(f"- layer {n}")
    if d["layers"]["order_changed"]: L.append("~ layer order changed")
    for n, ch in d["layers"]["changed"].items():
        L.append(f"~ layer {n}")
        if "tiles" in ch:
            t = ch["tiles"]; L.append(f"    tiles: {t['changed']} cells changed ({t['added']} filled, {t['cleared']} cleared) in bbox {t['bbox']}; top swaps " + ", ".join(f"{a}->{b} x{c}" for a, b, c in t["top_swaps"]))
        if "objects" in ch:
            o = ch["objects"]
            for x in o["added"]: L.append(f"    + object #{x['id']} {x['name']!r} {x['type']} at ({x['x']}, {x['y']})")
            for x in o["removed"]: L.append(f"    - object #{x['id']} {x['name']!r} {x['type']}")
            for x in o["moved"]: L.append(f"    ~ object #{x['id']} {x['name']!r} moved {x['from']} -> {x['to']}")
            for x in o["edited"]: L.append(f"    ~ object #{x['id']} {x['name']!r}: " + "; ".join(f"{f} {v}" if f != "properties" else "props " + str(v) for f, v in x["changes"].items()))
        for k in ("type", "visible", "opacity", "offsetx", "offsety"):
            if k in ch: L.append(f"    {k}: {ch[k][0]} -> {ch[k][1]}")
        if "properties" in ch: L.append("    properties: " + "; ".join(f"{p}: {x[0]!r} -> {x[1]!r}" for p, x in ch["properties"].items()))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff two Tiled JSON maps.")
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--md"); ap.add_argument("--json"); ap.add_argument("--fail-on-diff", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('old', 'new')
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    d = diff(json.load(open(a.old)), json.load(open(a.new)))
    L = lines(d); print("\n".join(L) if L else "no differences")
    if a.md: open(a.md, "w").write("# Map diff\n\n" + ("\n".join("- " + l.strip() if not l.startswith("    ") else "  - " + l.strip() for l in L) if L else "No differences.") + "\n")
    if a.json: json.dump(d, open(a.json, "w"), indent=1)
    return 1 if a.fail_on_diff and d["has_changes"] else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
