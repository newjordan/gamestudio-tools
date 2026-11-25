#!/usr/bin/env python3
"""tileset-split: split a packed Tiled tileset into two tilesets (the inverse of
tileset-merge). `--at N` puts local ids 0..N-1 in A and the rest in B; `--ids`
takes an explicit A-set (the rest is B). Image tilesets are repacked into two
sheets; collection tilesets split their `tiles` arrays. Tile metadata (type,
animation, objectgroup) and wangsets go with their tiles; an animation that
crosses the split is dropped and reported. With `--map`, the map's tileset
entry is replaced by two and GIDs are remapped when the split is not a simple
prefix. Inputs are never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tileset-merge"))
import safe_out, map_diff, tileset_merge  # noqa: E402

MASK = tileset_merge.MASK
FLAGS = tileset_merge.FLAGS


def parse_ids(spec):
    if os.path.isfile(spec):
        text = open(spec, encoding="utf-8").read().strip()
        if text.startswith("[") or text.startswith("{"):
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get("ids") or data.get("a") or []
            return [int(x) for x in data]
        spec = text.replace("\n", ",")
    return [int(x.strip()) for x in spec.split(",") if x.strip()]


def prefix_paths(out, stem):
    if out.endswith(os.sep) or os.path.isdir(out):
        os.makedirs(out, exist_ok=True)
        base = os.path.join(out, stem)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
        base = out
    return base + "_a.tsj", base + "_b.tsj", base + "_a.png", base + "_b.png"


def filter_tiles(tiles, id_map, warnings):
    out = []
    for t in tiles or []:
        oid = int(t.get("id", 0))
        if oid not in id_map:
            continue
        t = json.loads(json.dumps(t))
        t["id"] = id_map[oid]
        if "animation" in t:
            frames, ok = [], True
            for f in t["animation"]:
                tid = int(f.get("tileid", 0))
                if tid not in id_map:
                    ok = False
                    break
                f = dict(f)
                f["tileid"] = id_map[tid]
                frames.append(f)
            if ok:
                t["animation"] = frames
            else:
                t.pop("animation", None)
                warnings.append(f"dropped animation on tile {oid}: frames cross the split")
        out.append(t)
    return out


def filter_wangsets(wangsets, id_map):
    out = []
    for ws in wangsets or []:
        ws = json.loads(json.dumps(ws))
        kept = []
        for w in ws.get("wangtiles") or []:
            tid = int(w.get("tileid", 0))
            if tid in id_map:
                w = dict(w)
                w["tileid"] = id_map[tid]
                kept.append(w)
        if kept:
            ws["wangtiles"] = kept
            out.append(ws)
    return out


def build_half(ts, ids, name, images, columns, warnings):
    tw, th = int(ts["tilewidth"]), int(ts["tileheight"])
    id_map = {oid: i for i, oid in enumerate(ids)}
    tiles = filter_tiles(ts.get("tiles") or [], id_map, warnings)
    wang = filter_wangsets(ts.get("wangsets") or [], id_map)
    half = {"name": name, "tilewidth": tw, "tileheight": th, "tilecount": len(ids)}
    if tileset_merge.is_collection(ts):
        half["columns"] = 0
        # remap tile images stay as-is; only ids change
        half["tiles"] = tiles
        if wang:
            half["wangsets"] = wang
        return half, None
    margin, spacing = int(ts.get("margin") or 0), int(ts.get("spacing") or 0)
    cols = int(columns or ts.get("columns") or 1)
    cols = max(1, min(cols, len(ids)))
    chosen = [images[i] for i in ids]
    sheet, cols, rows = tileset_merge.pack_sheet(chosen, tw, th, cols, margin=margin, spacing=spacing)
    half.update({"columns": cols, "margin": margin, "spacing": spacing,
                 "imagewidth": sheet.width, "imageheight": sheet.height})
    if tiles:
        half["tiles"] = tiles
    if wang:
        half["wangsets"] = wang
    return half, sheet


def remap_gid_split(gid, first, id_map_a, id_map_b, first_a, first_b):
    if not gid:
        return 0
    tid, flags = gid & MASK, gid & FLAGS
    loc = tid - first
    if loc in id_map_a:
        return (first_a + id_map_a[loc]) | flags
    if loc in id_map_b:
        return (first_b + id_map_b[loc]) | flags
    return gid


def remap_map(m, first, count, ids_a, ids_b, entry_a, entry_b, source_a, source_b):
    m = json.loads(json.dumps(m))
    decoded = map_diff.decode_map(m)
    id_map_a = {oid: i for i, oid in enumerate(ids_a)}
    id_map_b = {oid: i for i, oid in enumerate(ids_b)}
    first_a = first
    first_b = first + len(ids_a)
    prefix = ids_a == list(range(len(ids_a))) and ids_b == list(range(len(ids_a), len(ids_a) + len(ids_b)))

    def walk(layers):
        out = []
        for l in layers or []:
            l = dict(l)
            if l.get("type") == "group":
                l["layers"] = walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer" and "data" in l:
                if prefix:
                    l["data"] = list(l["data"])
                else:
                    l["data"] = [remap_gid_split(int(g), first, id_map_a, id_map_b, first_a, first_b)
                                 for g in l["data"]]
                l.pop("encoding", None)
                l.pop("compression", None)
            elif l.get("type") == "objectgroup" or "objects" in l:
                objs = []
                for o in l.get("objects") or []:
                    o = dict(o)
                    if o.get("gid"):
                        if not prefix:
                            o["gid"] = remap_gid_split(int(o["gid"]), first, id_map_a, id_map_b, first_a, first_b)
                    objs.append(o)
                l["objects"] = objs
            out.append(l)
        return out

    decoded["layers"] = walk(decoded.get("layers") or [])
    sets, kept, hit = [], [], False
    for ts in decoded.get("tilesets") or []:
        if not hit and int(ts.get("firstgid") or 0) == first:
            ea = dict(entry_a)
            ea["firstgid"] = first_a
            ea["source"] = os.path.basename(source_a)
            ea.pop("image", None)
            eb = dict(entry_b)
            eb["firstgid"] = first_b
            eb["source"] = os.path.basename(source_b)
            eb.pop("image", None)
            sets.extend([ea, eb])
            hit = True
        else:
            sets.append(ts)
    if not hit:
        raise SystemExit(f"could not match tileset firstgid {first} on the map")
    decoded["tilesets"] = sets
    return decoded, first_a, first_b


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a Tiled tileset into two and optionally remap a map's GIDs.")
    ap.add_argument("tileset")
    ap.add_argument("-o", "--out", required=True, help="output prefix or directory (writes *_a.tsj and *_b.tsj)")
    ap.add_argument("--at", type=int, help="split after the first N tiles (ids 0..N-1 vs the rest)")
    ap.add_argument("--ids", help="comma list or JSON file of local ids for tileset A (rest is B)")
    ap.add_argument("--name-a")
    ap.add_argument("--name-b")
    ap.add_argument("--columns", type=int, help="columns in each packed sheet (default: source columns, capped)")
    ap.add_argument("--map", help="optional Tiled JSON map to remap")
    ap.add_argument("--map-out", help="remapped map path (required with --map)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if (a.at is None) == (a.ids is None):
        # default: midpoint if neither given? require one for clarity
        pass
    sources = [a.tileset] + ([a.map] if a.map else [])
    stem = os.path.splitext(os.path.basename(a.tileset))[0]
    path_a, path_b, img_a, img_b = prefix_paths(a.out, stem)
    for dest in (path_a, path_b, img_a, img_b, a.json, a.map_out):
        if dest:
            safe_out.check_any(sources, dest, a.in_place)
    if a.map and not a.map_out:
        sys.exit("--map requires --map-out")
    ts = tileset_merge.load_tileset(a.tileset)
    count = tileset_merge.tilecount_of(ts)
    images = None
    if not tileset_merge.is_collection(ts):
        images, _ = tileset_merge.extract_sheet_tiles(ts)
        if count is None:
            count = len(images)
    if count is None or count < 2:
        sys.exit("tileset needs at least two tiles to split")
    if a.ids:
        ids_a = parse_ids(a.ids)
        if a.at is not None:
            sys.exit("pass only one of --at or --ids")
    else:
        at = a.at if a.at is not None else count // 2
        if at <= 0 or at >= count:
            sys.exit(f"--at must be in 1..{count - 1}")
        ids_a = list(range(at))
    seen = set()
    for i in ids_a:
        if i < 0 or i >= count:
            sys.exit(f"id {i} is outside 0..{count - 1}")
        if i in seen:
            sys.exit(f"duplicate id {i}")
        seen.add(i)
    ids_b = [i for i in range(count) if i not in seen]
    if not ids_a or not ids_b:
        sys.exit("both sides of the split must have at least one tile")
    warnings = []
    name = ts.get("name") or stem
    half_a, sheet_a = build_half(ts, ids_a, a.name_a or (name + "_a"), images, a.columns, warnings)
    half_b, sheet_b = build_half(ts, ids_b, a.name_b or (name + "_b"), images, a.columns, warnings)
    if sheet_a is not None:
        sheet_a.save(img_a)
        half_a["image"] = os.path.relpath(img_a, os.path.dirname(os.path.abspath(path_a)) or ".")
    if sheet_b is not None:
        sheet_b.save(img_b)
        half_b["image"] = os.path.relpath(img_b, os.path.dirname(os.path.abspath(path_b)) or ".")
    json.dump(half_a, open(path_a, "w"), indent=2)
    json.dump(half_b, open(path_b, "w"), indent=2)
    rec = {"count": count, "ids_a": ids_a, "ids_b": ids_b, "out_a": path_a, "out_b": path_b,
           "warnings": warnings}
    if a.map:
        raw = json.load(open(a.map, encoding="utf-8"))
        decoded = map_diff.decode_map(raw)
        first = None
        for ts_e in decoded.get("tilesets") or []:
            if tileset_merge.match_map_tileset(ts_e, a.tileset, ts.get("name")):
                first = int(ts_e["firstgid"])
                break
        if first is None:
            sys.exit("could not match the tileset on the map (by source basename or name)")
        out_m, fa, fb = remap_map(raw, first, count, ids_a, ids_b, half_a, half_b, path_a, path_b)
        json.dump(out_m, open(a.map_out, "w"), indent=2)
        rec["map_out"] = a.map_out
        rec["firstgid_a"] = fa
        rec["firstgid_b"] = fb
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"split {count} tile(s) -> {len(ids_a)} + {len(ids_b)} ({path_a}, {path_b})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
