#!/usr/bin/env python3
"""tileset-merge: combine two Tiled tileset files (JSON / TSJ / TSX) into one and optionally
remap a map's GIDs so it points at the merged tileset. Image tilesets with the same tile size
are packed into a new sheet (A's tiles, then B's); collection tilesets concatenate their `tiles`
arrays with remapped ids and animation `tileid`s. Tile metadata (type, animation) is preserved
with ids shifted by A's tilecount. Writes a new tileset (and optional map / sheet); inputs are
never overwritten unless `--in-place`. Mixed image/collection tilesets, or different tile sizes,
are refused.
"""
import argparse, os, json, math, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLAGS = 0xE0000000


def load_tileset(path):
    low = path.lower()
    if low.endswith((".tsx", ".xml")):
        ts = map_diff.load_tsx(path)
    else:
        ts = json.load(open(path, encoding="utf-8"))
        if ts.get("type") == "map":
            raise SystemExit(f"{path} looks like a map, not a tileset")
    ts = dict(ts)
    ts["_path"] = os.path.abspath(path)
    img = ts.get("image")
    if img and not os.path.isabs(img):
        ts["image"] = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(path)), img))
    return ts


def tilecount_of(ts):
    if ts.get("tilecount"):
        return int(ts["tilecount"])
    tiles = ts.get("tiles") or []
    if tiles:
        return max(int(t.get("id", 0)) for t in tiles) + 1
    if ts.get("image") and ts.get("columns") and ts.get("tilewidth") and ts.get("tileheight"):
        # estimate from image later
        return None
    raise SystemExit(f"tileset {ts.get('name')!r} has no tilecount")


def extract_sheet_tiles(ts):
    path = ts.get("image")
    if not path or not os.path.isfile(path):
        raise SystemExit(f"tileset image not found: {path}")
    im = Image.open(path).convert("RGBA")
    tw, th = int(ts["tilewidth"]), int(ts["tileheight"])
    margin, spacing = int(ts.get("margin") or 0), int(ts.get("spacing") or 0)
    cols = int(ts.get("columns") or 0)
    if cols <= 0:
        cols = max(1, (im.width - margin + spacing) // (tw + spacing))
    count = tilecount_of(ts)
    if count is None:
        rows = max(1, (im.height - margin + spacing) // (th + spacing))
        count = cols * rows
    out = []
    for i in range(count):
        c, r = i % cols, i // cols
        x = margin + c * (tw + spacing)
        y = margin + r * (th + spacing)
        out.append(im.crop((x, y, x + tw, y + th)))
    return out, cols


def pack_sheet(tiles, tw, th, columns, margin=0, spacing=0):
    columns = max(1, int(columns))
    rows = max(1, math.ceil(len(tiles) / columns))
    w = margin * 2 + columns * tw + spacing * max(0, columns - 1)
    h = margin * 2 + rows * th + spacing * max(0, rows - 1)
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i, tile in enumerate(tiles):
        c, r = i % columns, i // columns
        x = margin + c * (tw + spacing)
        y = margin + r * (th + spacing)
        sheet.paste(tile, (x, y))
    return sheet, columns, rows


def remap_tile_meta(tiles, offset):
    out = []
    for t in tiles or []:
        t = dict(t)
        t["id"] = int(t.get("id", 0)) + offset
        if "animation" in t:
            frames = []
            for f in t["animation"]:
                f = dict(f)
                f["tileid"] = int(f.get("tileid", 0)) + offset
                frames.append(f)
            t["animation"] = frames
        t.pop("image", None)
        t.pop("imagewidth", None)
        t.pop("imageheight", None)
        out.append(t)
    return out


def remap_wangsets(wangsets, offset):
    out = []
    for ws in wangsets or []:
        ws = json.loads(json.dumps(ws))
        for w in ws.get("wangtiles") or []:
            if "tileid" in w:
                w["tileid"] = int(w["tileid"]) + offset
        out.append(ws)
    return out


def is_collection(ts):
    return not ts.get("image") and bool(ts.get("tiles"))


def merge_tilesets(a, b, name, columns=None):
    tw, th = int(a.get("tilewidth") or 0), int(a.get("tileheight") or 0)
    if (int(b.get("tilewidth") or 0), int(b.get("tileheight") or 0)) != (tw, th) or not tw or not th:
        raise SystemExit("tilesets must share a positive tile width and height")
    col_a, col_b = is_collection(a), is_collection(b)
    if col_a != col_b:
        raise SystemExit("cannot merge an image tileset with a collection tileset")
    ca = tilecount_of(a)
    cb = tilecount_of(b)
    if col_a:
        if ca is None or cb is None:
            raise SystemExit("collection tilesets need a tilecount or tiles[].id")
        tiles = remap_tile_meta(a.get("tiles") or [], 0) + remap_tile_meta(b.get("tiles") or [], ca)
        merged = {
            "name": name, "tilewidth": tw, "tileheight": th,
            "tilecount": ca + cb, "columns": 0, "tiles": tiles,
        }
        if a.get("wangsets") or b.get("wangsets"):
            merged["wangsets"] = list(a.get("wangsets") or []) + remap_wangsets(b.get("wangsets") or [], ca)
        return merged, None, ca, cb
    tiles_a, cols_a = extract_sheet_tiles(a)
    tiles_b, cols_b = extract_sheet_tiles(b)
    if ca is None:
        ca = len(tiles_a)
    if cb is None:
        cb = len(tiles_b)
    cols = int(columns or a.get("columns") or cols_a or 1)
    sheet, cols, rows = pack_sheet(tiles_a + tiles_b, tw, th, cols,
                                   margin=int(a.get("margin") or 0),
                                   spacing=int(a.get("spacing") or 0))
    tiles = remap_tile_meta(a.get("tiles") or [], 0) + remap_tile_meta(b.get("tiles") or [], ca)
    merged = {
        "name": name, "tilewidth": tw, "tileheight": th,
        "tilecount": ca + cb, "columns": cols,
        "margin": int(a.get("margin") or 0), "spacing": int(a.get("spacing") or 0),
        "imagewidth": sheet.width, "imageheight": sheet.height,
    }
    if tiles:
        merged["tiles"] = tiles
    if a.get("wangsets") or b.get("wangsets"):
        merged["wangsets"] = list(a.get("wangsets") or []) + remap_wangsets(b.get("wangsets") or [], ca)
    return merged, sheet, ca, cb


def match_map_tileset(ts, path, name):
    src = ts.get("source") or ""
    if src and os.path.basename(src) == os.path.basename(path):
        return True
    if ts.get("name") and name and ts.get("name") == name:
        return True
    if ts.get("image") and os.path.basename(str(ts.get("image"))) == os.path.basename(path):
        return True
    return False


def remap_gid(gid, ranges, new_first):
    if not gid:
        return 0
    tid, flags = gid & MASK, gid & FLAGS
    for first, count, offset in ranges:
        if first <= tid < first + count:
            return (new_first + offset + (tid - first)) | flags
    return gid


def remap_map(m, ranges, new_ts, firstgid=1):
    m = dict(m)

    def walk(layers):
        out = []
        for l in layers or []:
            l = dict(l)
            if l.get("type") == "group":
                l["layers"] = walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer" and "data" in l:
                l["data"] = [remap_gid(int(g), ranges, firstgid) for g in l["data"]]
                l.pop("encoding", None)
                l.pop("compression", None)
            elif l.get("type") == "objectgroup" or "objects" in l:
                objs = []
                for o in l.get("objects") or []:
                    o = dict(o)
                    if o.get("gid"):
                        o["gid"] = remap_gid(int(o["gid"]), ranges, firstgid)
                    objs.append(o)
                l["objects"] = objs
            out.append(l)
        return out

    m["layers"] = walk(m.get("layers") or [])
    kept, consumed = [], set()
    for ts in m.get("tilesets") or []:
        hit = False
        for i, (first, count, offset) in enumerate(ranges):
            if ts.get("firstgid") == first:
                consumed.add(i)
                hit = True
                break
        if not hit:
            kept.append(ts)
    merged_entry = dict(new_ts)
    merged_entry["firstgid"] = firstgid
    m["tilesets"] = [merged_entry] + kept
    return m, sorted(consumed)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge two Tiled tilesets and optionally remap a map's GIDs.")
    ap.add_argument("tileset_a")
    ap.add_argument("tileset_b")
    ap.add_argument("-o", "--out", required=True, help="merged tileset JSON path")
    ap.add_argument("--image", help="merged sheet path (default: alongside -o, same stem + .png)")
    ap.add_argument("--name", help="merged tileset name (default: stem of -o)")
    ap.add_argument("--columns", type=int, help="columns in the packed sheet (default: A's columns)")
    ap.add_argument("--map", help="optional Tiled JSON map whose GIDs should be remapped")
    ap.add_argument("--map-out", help="remapped map path (required with --map)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    sources = [a.tileset_a, a.tileset_b] + ([a.map] if a.map else [])
    safe_out.check_any(sources, a.out, a.in_place)
    if a.image:
        safe_out.check_any(sources, a.image, a.in_place)
    if a.map_out:
        safe_out.check_any(sources, a.map_out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    if a.map and not a.map_out:
        sys.exit("--map requires --map-out")
    ts_a, ts_b = load_tileset(a.tileset_a), load_tileset(a.tileset_b)
    name = a.name or os.path.splitext(os.path.basename(a.out))[0]
    merged, sheet, ca, cb = merge_tilesets(ts_a, ts_b, name, a.columns)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    if sheet is not None:
        img_path = a.image or (os.path.splitext(os.path.abspath(a.out))[0] + ".png")
        os.makedirs(os.path.dirname(img_path) or ".", exist_ok=True)
        sheet.save(img_path)
        merged["image"] = os.path.relpath(img_path, os.path.dirname(os.path.abspath(a.out)) or ".")
    json.dump(merged, open(a.out, "w"), indent=2)
    rec = {"name": name, "tilecount": merged["tilecount"], "count_a": ca, "count_b": cb, "out": a.out}
    if a.map:
        raw = json.load(open(a.map, encoding="utf-8"))
        decoded = map_diff.decode_map(raw)
        sets = decoded.get("tilesets") or []
        ia = ib = None
        for i, ts in enumerate(sets):
            if ia is None and match_map_tileset(ts, a.tileset_a, ts_a.get("name")):
                ia = i
            elif ib is None and match_map_tileset(ts, a.tileset_b, ts_b.get("name")):
                ib = i
        if ia is None or ib is None:
            raise SystemExit("could not match both tilesets on the map (by source basename or name)")
        fa, fb = int(sets[ia]["firstgid"]), int(sets[ib]["firstgid"])
        ranges = [(fa, ca, 0), (fb, cb, ca)]
        firstgid = min(fa, fb)
        out_ts = dict(merged)
        if "image" in out_ts and a.map_out:
            img = out_ts["image"]
            abs_img = img if os.path.isabs(img) else os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(a.out)), img))
            try:
                out_ts["image"] = os.path.relpath(abs_img, os.path.dirname(os.path.abspath(a.map_out)) or ".")
            except ValueError:
                out_ts["image"] = abs_img
        m, _ = remap_map(decoded, ranges, out_ts, firstgid=firstgid)
        os.makedirs(os.path.dirname(os.path.abspath(a.map_out)) or ".", exist_ok=True)
        json.dump(m, open(a.map_out, "w"), indent=2)
        rec["map_out"] = a.map_out
        rec["firstgid"] = firstgid
    print(f"{ca}+{cb} tile(s) -> {merged['tilecount']} {a.out}" + (f", map {a.map_out}" if a.map else ""))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
