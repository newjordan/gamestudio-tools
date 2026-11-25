#!/usr/bin/env python3
"""tileset-wang: write a Tiled tileset JSON with a wang set so Tiled can terrain-paint from an autotile-gen (16-tile
edge) or tileset-gen (47-tile blob) sheet. Colour 1 is the inner terrain; 0 is "none" (outer). The 47-tile blob uses a
mixed (edge+corner) wang set in tileset-gen CANON order; the 16-tile set uses an edge wang set in bitmask order
(N=1,E=2,S=4,W=8). Input is a tileset-gen / autotile-gen meta JSON, a Tiled tileset JSON (wangsets are added), or
--kind blob|edge with --image. Writes a new JSON; the input is never overwritten.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tileset-gen"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "autotile-gen"))
import tileset_gen  # noqa: E402

# Tiled wangid: [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
# tileset-gen bits: N=1 NE=2 E=4 SE=8 S=16 SW=32 W=64 NW=128
BLOB_BITS = (tileset_gen.N, tileset_gen.NE, tileset_gen.E, tileset_gen.SE,
             tileset_gen.S, tileset_gen.SW, tileset_gen.W, tileset_gen.NW)
# autotile-gen 4-bit: N, E, S, W typically 1,2,4,8 — confirmed in autotile_gen bitmask field
EDGE_INDEX = {0: 0, 2: 1, 4: 2, 6: 3}  # wangid slots for N,E,S,W


def wangid_from_blob_mask(m):
    return [1 if m & bit else 0 for bit in BLOB_BITS]


def wangid_from_edge_mask(m, bits):
    # bits dict N,E,S,W
    n, e, s, w = bits.get("N", 1), bits.get("E", 2), bits.get("S", 4), bits.get("W", 8)
    wid = [0] * 8
    wid[0] = 1 if m & n else 0
    wid[2] = 1 if m & e else 0
    wid[4] = 1 if m & s else 0
    wid[6] = 1 if m & w else 0
    return wid


def detect(meta):
    if "lookup" in meta and int(meta.get("count") or 0) >= 40:
        return "blob"
    if "bitmask" in meta or int(meta.get("count") or meta.get("tilecount") or 0) == 16:
        return "edge"
    if meta.get("wangsets"):
        return "tiled"
    return None


def blob_tiles(meta=None):
    tiles = []
    if meta and meta.get("tiles"):
        # tiles may be keyed by index str
        for i, m in enumerate(tileset_gen.CANON):
            rec = meta["tiles"].get(str(i)) or meta["tiles"].get(i) or {}
            mask = rec.get("mask", m)
            tiles.append({"tileid": i, "wangid": wangid_from_blob_mask(mask)})
        return tiles
    for i, m in enumerate(tileset_gen.CANON):
        tiles.append({"tileid": i, "wangid": wangid_from_blob_mask(m)})
    return tiles


def edge_tiles(meta=None):
    bits = (meta or {}).get("bitmask") or {"N": 1, "E": 2, "S": 4, "W": 8}
    tiles = []
    src = (meta or {}).get("tiles") or {}
    if src:
        # autotile-gen stores mask -> {index,x,y} or index -> {mask,x,y}
        # read autotile format: meta["tiles"] keys are str(mask) with index
        inverted = {}
        for k, rec in src.items():
            if "index" in rec: inverted[int(rec["index"])] = rec.get("mask", int(k) if str(k).isdigit() else 0)
            elif "mask" in rec: inverted[int(k)] = rec["mask"]
            else:
                try: inverted[int(k)] = int(k)
                except ValueError: pass
        if inverted:
            for i in sorted(inverted):
                tiles.append({"tileid": i, "wangid": wangid_from_edge_mask(inverted[i], bits)})
            return tiles
    for m in range(16):
        tiles.append({"tileid": m, "wangid": wangid_from_edge_mask(m, bits)})
    return tiles


def build(kind, image, tile, columns, count, name, terrain, meta=None, base=None):
    ts = dict(base) if base else {"name": name or "wang", "tilewidth": tile, "tileheight": tile,
                                  "tilecount": count, "columns": columns, "image": image or ""}
    if image: ts["image"] = image
    ts.setdefault("tilewidth", tile); ts.setdefault("tileheight", tile)
    ts.setdefault("tilecount", count); ts.setdefault("columns", columns)
    ts.setdefault("name", name or ts.get("name") or "wang")
    color = {"name": terrain or "terrain", "color": "#4a8f3c", "probability": 1}
    if kind == "blob":
        wtiles = blob_tiles(meta)
        wtype = "mixed"
    else:
        wtiles = edge_tiles(meta)
        wtype = "edge"
    ts["wangsets"] = [{
        "name": terrain or kind,
        "type": wtype,
        "colors": [color],
        "wangtiles": wtiles,
    }]
    return ts


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Tiled wang-set JSON from an autotile / blob sheet.")
    ap.add_argument("input", nargs="?", help="tileset-gen / autotile-gen meta JSON, or a Tiled tileset JSON")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--kind", choices=("blob", "edge"), help="override auto-detect (or required when no input JSON)")
    ap.add_argument("--image", help="tileset image path written into the JSON")
    ap.add_argument("--tile", type=int, default=16)
    ap.add_argument("--columns", type=int)
    ap.add_argument("--name", default="wang")
    ap.add_argument("--terrain", default="terrain")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.input or a.out) and not a.in_place and a.input:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    meta = base = None
    kind = a.kind
    image, tile, columns, count = a.image, a.tile, a.columns, None
    if a.input:
        meta = json.load(open(a.input, encoding="utf-8"))
        kind = kind or detect(meta) or sys.exit("could not detect kind; pass --kind blob or --edge")
        image = image or meta.get("image") or (os.path.splitext(a.input)[0] + ".png" if not meta.get("lookup") and not meta.get("bitmask") else None)
        # tileset-gen writes sibling .png when -o basename is used; if input is foo.json try foo.png
        if not image:
            sib = os.path.splitext(a.input)[0] + ".png"
            image = os.path.basename(sib)
        tile = meta.get("tile") or meta.get("tilewidth") or tile
        columns = columns or meta.get("columns")
        count = meta.get("count") or meta.get("tilecount")
        if meta.get("tilewidth") and meta.get("wangsets") is not None or (meta.get("type") == "tileset") or "wangsets" in meta or (meta.get("tilecount") and meta.get("image") and not meta.get("lookup") and not meta.get("bitmask")):
            # starting from a Tiled tileset: copy it and add wangsets
            if "lookup" not in meta and "bitmask" not in meta:
                base = {k: v for k, v in meta.items() if k != "wangsets"}
                count = base.get("tilecount") or count
                columns = columns or base.get("columns")
                image = a.image or base.get("image") or image
                tile = base.get("tilewidth") or tile
    if kind is None: sys.exit("pass --kind blob or --kind edge (or a meta JSON)")
    if kind == "blob":
        columns = columns or 8; count = count or 47
    else:
        columns = columns or 4; count = count or 16
    ts = build(kind, image, int(tile), int(columns), int(count), a.name, a.terrain, meta=meta, base=base)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(ts, open(a.out, "w"), indent=(2 if a.pretty else 1))
    n = len(ts["wangsets"][0]["wangtiles"])
    print(f"{kind} wang set, {n} tile(s), type {ts['wangsets'][0]['type']} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
