#!/usr/bin/env python3
"""tileset-renumber: remap local tile ids in a Tiled tileset JSON (and optionally
the GIDs in one or more maps that use it). `--offset` adds N to every local id in
range, or `--remap` takes a JSON/CSV table of old=new local ids (same shapes as
tile-replace). Animation `tileid`s, wang tiles, and per-tile object groups follow
the new ids. Map GIDs keep flip flags. The tileset (and maps) are never
overwritten unless `--in-place`.
"""
import argparse, os, copy, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-replace"))
import safe_out, map_diff, tile_replace  # noqa: E402


def load_table(spec, offset, tilecount):
    if (spec is None) == (offset is None):
        raise SystemExit("pass exactly one of --offset or --remap")
    if offset is not None:
        n = max(int(tilecount or 0), 0)
        return {i: i + offset for i in range(n)}
    if os.path.isfile(spec):
        return tile_replace.load_table(spec)
    # inline 0=2,1=0
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part and ":" not in part:
            raise SystemExit(f"bad remap token {part!r}; use old=new or a JSON/CSV file")
        a, b = part.replace(":", "=", 1).split("=", 1)
        out[int(a)] = int(b)
    if not out:
        raise SystemExit("remap table is empty")
    return out


def remap_tileset(ts, table):
    n = 0
    tiles = ts.get("tiles") or []
    for t in tiles:
        oid = int(t.get("id", 0))
        if oid in table:
            t["id"] = table[oid]
            n += 1
        for frame in t.get("animation") or []:
            tid = int(frame.get("tileid", frame.get("id", 0)))
            if tid in table:
                frame["tileid"] = table[tid]
                if "id" in frame and "tileid" in frame:
                    pass
    for ws in ts.get("wangsets") or []:
        for wt in ws.get("wangtiles") or []:
            tid = int(wt.get("tileid", wt.get("id", 0)))
            if tid in table:
                wt["tileid"] = table[tid]
                n += 1
    return n


def firstgids_for(m, name=None, source=None, firstgid=None):
    if firstgid is not None:
        return [int(firstgid)]
    hits = []
    for ts in m.get("tilesets") or []:
        if name and ts.get("name") == name:
            hits.append(int(ts.get("firstgid") or 1))
        elif source and os.path.basename(str(ts.get("source") or ts.get("image") or "")) == os.path.basename(source):
            hits.append(int(ts.get("firstgid") or 1))
    if not hits:
        # single tileset, unambiguous
        tss = m.get("tilesets") or []
        if len(tss) == 1:
            return [int(tss[0].get("firstgid") or 1)]
        raise SystemExit("could not match a tileset on the map; pass --firstgid or --tileset-name")
    return hits


def gid_table(local, firstgids, tilecount):
    # map every firstgid+old_local -> firstgid+new_local (flags applied later)
    out = {}
    for fg in firstgids:
        for old, new in local.items():
            out[fg + old] = (fg + new) if new else 0
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Remap local tile ids in a Tiled tileset, and optionally map GIDs.")
    ap.add_argument("tileset", help="Tiled tileset JSON (.json / .tsj)")
    ap.add_argument("-o", "--out", required=True, help="output tileset JSON")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--offset", type=int, help="add N to every local id in 0..tilecount-1")
    g.add_argument("--remap", help="JSON/CSV table or inline old=new,old=new of local ids")
    ap.add_argument("--map", action="append", default=[], help="Tiled map JSON to rewrite (repeatable)")
    ap.add_argument("--map-out", help="output path when a single --map is given; default: <stem>_renumber.json next to --out")
    ap.add_argument("--map-outdir", help="directory for rewritten maps when several --map are given")
    ap.add_argument("--firstgid", type=int, help="firstgid of this tileset on the map (if not discoverable)")
    ap.add_argument("--tileset-name", help="match map.tilesets[].name")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    ts_path = a.tileset
    safe_out.check(ts_path, a.out, a.in_place)
    if a.json:
        safe_out.check(ts_path, a.json, a.in_place)
    ts = json.load(open(ts_path, encoding="utf-8"))
    table = load_table(a.remap, a.offset, ts.get("tilecount") or ts.get("count") or 0)
    ts2 = copy.deepcopy(ts)
    n_ts = remap_tileset(ts2, table)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(ts2, open(a.out, "w"), indent=2)
    maps_out = []
    for mp in a.map:
        raw = json.load(open(mp, encoding="utf-8"))
        decoded = map_diff.decode_map(copy.deepcopy(raw))
        fgs = firstgids_for(decoded, a.tileset_name, ts_path, a.firstgid)
        gtable = gid_table(table, fgs, ts.get("tilecount"))
        new_m, rec = tile_replace.replace_map(decoded, gtable, "keep")
        if len(a.map) == 1:
            dest = a.map_out or os.path.join(os.path.dirname(os.path.abspath(a.out)),
                                             os.path.splitext(os.path.basename(mp))[0] + "_renumber.json")
        else:
            od = a.map_outdir or os.path.dirname(os.path.abspath(a.out))
            os.makedirs(od, exist_ok=True)
            dest = os.path.join(od, os.path.splitext(os.path.basename(mp))[0] + "_renumber.json")
        safe_out.check(mp, dest, a.in_place)
        json.dump(new_m, open(dest, "w"), indent=2)
        maps_out.append({"map": mp, "out": dest, "firstgids": fgs, "cells_changed": rec["cells_changed"]})
    report = {"tileset_out": a.out, "local_ids": len(table), "tileset_rewrites": n_ts, "maps": maps_out}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(report, open(a.json, "w"), indent=2)
    extra = f", {len(maps_out)} map(s)" if maps_out else ""
    print(f"{len(table)} local id(s) remapped{extra} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
