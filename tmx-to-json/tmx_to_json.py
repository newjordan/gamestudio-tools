#!/usr/bin/env python3
"""tmx-to-json: convert Tiled TMX (XML) maps to Tiled JSON.

Handles map attributes and properties, tilesets (embedded, or external via `source`, kept as a reference),
tile layers (csv, base64 uncompressed / zlib / gzip / zstd), object groups (rectangles, points,
ellipses, polygons, polylines, text kept as plain objects) and group layers. Output follows the documented Tiled
JSON map format; run it through tilemap-convert / tile-colliders / asset-viewer like any other map.
"""
import os
import argparse, base64, gzip, json, struct, sys, zlib
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import zstd_pure  # noqa: E402


def num(v):
    try:
        f = float(v); return int(f) if f == int(f) and "." not in v else f
    except (TypeError, ValueError):
        return v


def props(el):
    out = []
    p = el.find("properties")
    if p is None: return out
    for x in p.findall("property"):
        t = x.get("type", "string"); v = x.get("value", x.text or "")
        v = {"int": lambda s: int(s), "float": lambda s: float(s), "bool": lambda s: s == "true"}.get(t, lambda s: s)(v)
        out.append({"name": x.get("name"), "type": t, "value": v})
    return out


def layer_data(el, w, h):
    d = el.find("data"); enc, comp = d.get("encoding"), d.get("compression")
    if enc == "csv": return [int(x) for x in d.text.replace("\n", "").split(",") if x.strip()]
    if enc == "base64":
        raw = base64.b64decode(d.text.strip())
        if comp in ("zlib", "gzip"):
            try:
                raw = (zlib if comp == "zlib" else gzip).decompress(raw)
            except (zlib.error, OSError, EOFError) as e:
                raise GstInputError(f"{comp} tile data is corrupt ({e})") from e
        elif comp == "zstd": raw = zstd_pure.decompress_auto(raw)
        elif comp: raise SystemExit(f"unsupported compression {comp!r}")
        return list(struct.unpack(f"<{len(raw) // 4}I", raw))
    if enc is None: return [int(t.get("gid", 0)) for t in d.findall("tile")]
    raise SystemExit(f"unsupported encoding {enc!r}")


def convert_layer(el, ids):
    base = {"id": int(el.get("id", next(ids))), "name": el.get("name", ""), "x": 0, "y": 0, "opacity": float(el.get("opacity", 1)), "visible": el.get("visible", "1") != "0"}
    if el.tag == "layer":
        w, h = int(el.get("width")), int(el.get("height"))
        return {**base, "type": "tilelayer", "width": w, "height": h, "data": layer_data(el, w, h), **({"properties": props(el)} if props(el) else {})}
    if el.tag == "objectgroup":
        objs = []
        for o in el.findall("object"):
            ob = {"id": int(o.get("id", 0)), "name": o.get("name", ""), "type": o.get("type", o.get("class", "")), "x": num(o.get("x", "0")), "y": num(o.get("y", "0")),
                  "width": num(o.get("width", "0")), "height": num(o.get("height", "0")), "rotation": num(o.get("rotation", "0")), "visible": o.get("visible", "1") != "0"}
            if o.get("gid"): ob["gid"] = int(o.get("gid"))
            if o.find("point") is not None: ob["point"] = True
            if o.find("ellipse") is not None: ob["ellipse"] = True
            for tag in ("polygon", "polyline"):
                p = o.find(tag)
                if p is not None: ob[tag] = [{"x": num(a.split(",")[0]), "y": num(a.split(",")[1])} for a in p.get("points").split()]
            if props(o): ob["properties"] = props(o)
            objs.append(ob)
        return {**base, "type": "objectgroup", "draworder": el.get("draworder", "topdown"), "objects": objs}
    if el.tag == "imagelayer":
        im = el.find("image"); return {**base, "type": "imagelayer", "image": im.get("source") if im is not None else ""}
    if el.tag == "group":
        return {**base, "type": "group", "layers": [convert_layer(c, ids) for c in el if c.tag in ("layer", "objectgroup", "imagelayer", "group")]}
    return None


def convert(path):
    root = ET.parse(path).getroot()
    if root.tag != "map": raise SystemExit("not a TMX map")
    ids = iter(range(1, 10 ** 6))
    m = {"type": "map", "version": root.get("version", "1.10"), "tiledversion": root.get("tiledversion", ""), "orientation": root.get("orientation", "orthogonal"),
         "renderorder": root.get("renderorder", "right-down"), "width": int(root.get("width")), "height": int(root.get("height")),
         "tilewidth": int(root.get("tilewidth")), "tileheight": int(root.get("tileheight")), "infinite": root.get("infinite", "0") == "1",
         "nextlayerid": int(root.get("nextlayerid", 1)), "nextobjectid": int(root.get("nextobjectid", 1))}
    m["tilesets"] = []
    for ts in root.findall("tileset"):
        t = {"firstgid": int(ts.get("firstgid"))}
        if ts.get("source"): t["source"] = ts.get("source")
        else:
            im = ts.find("image")
            t.update({"name": ts.get("name", ""), "tilewidth": int(ts.get("tilewidth")), "tileheight": int(ts.get("tileheight")), "tilecount": int(ts.get("tilecount", 0)),
                      "columns": int(ts.get("columns", 0)), "margin": int(ts.get("margin", 0)), "spacing": int(ts.get("spacing", 0))})
            if im is not None: t.update({"image": im.get("source"), "imagewidth": int(im.get("width", 0)), "imageheight": int(im.get("height", 0))})
        m["tilesets"].append(t)
    m["layers"] = [l for l in (convert_layer(c, ids) for c in root if c.tag in ("layer", "objectgroup", "imagelayer", "group")) if l]
    if props(root): m["properties"] = props(root)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tiled TMX to Tiled JSON.")
    ap.add_argument("tmx", nargs="+"); ap.add_argument("-o", "--out", help="output file (single input) or directory")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    import os
    for f in a.tmx:
        out = a.out if a.out and len(a.tmx) == 1 and not os.path.isdir(a.out) else os.path.join(a.out or os.path.dirname(f) or ".", os.path.splitext(os.path.basename(f))[0] + ".json")
        if os.path.abspath(out) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        m = convert(f); json.dump(m, open(out, "w"), indent=1)
        print(f"{f} -> {out}: {m['width']}x{m['height']}, {len(m['layers'])} layer(s), {len(m['tilesets'])} tileset(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
