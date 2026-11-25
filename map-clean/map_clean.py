#!/usr/bin/env python3
"""map-clean: tidy a Tiled JSON map for shipping or diffs: drop hidden layers, drop empty tile or object layers, drop
tilesets that no cell uses, and drop empty property lists. Remaining tilesets are packed to tight firstgids (1, then
1+tilecount, ...) and every tile-layer GID and object `gid` is remapped, flip flags kept. --keep-firstgids leaves the
original firstgids and cell values alone (a gap in firstgids is valid in Tiled). Group layers that become empty after
their children are dropped are removed too. Writes a new JSON (-o); the input is never overwritten. --pretty keeps
indentation; the default is compact JSON. Reports what was removed and any firstgid remap. Encoded (base64 zlib/gzip
or csv) tile data is decoded to plain arrays in the output; zstd is decoded when a decompressor is importable.
Infinite maps are supported.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tilemap-stats"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import tilemap_stats, map_diff  # noqa: E402

MASK = tilemap_stats.MASK
FLAGS = 0xE0000000


def used_gids(layers):
    used = set()
    def walk(ls):
        for l in ls:
            if l.get("type") == "group": walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                for g in tilemap_stats.gids_of(l):
                    if g & MASK: used.add(g & MASK)
            elif l.get("type") == "objectgroup":
                for o in l.get("objects") or []:
                    g = o.get("gid")
                    if g and (g & MASK): used.add(g & MASK)
    walk(layers); return used


def layer_empty(l):
    typ = l.get("type")
    if typ == "tilelayer":
        g = tilemap_stats.gids_of(l); return (not g) or all((x & MASK) == 0 for x in g)
    if typ == "objectgroup": return not l.get("objects")
    if typ == "imagelayer": return not l.get("image")
    if typ == "group": return not l.get("layers")
    return False


def clean_layers(layers, drop_hidden, drop_empty, report):
    out = []
    for l in layers:
        l = dict(l)
        if l.get("type") == "group":
            l["layers"] = clean_layers(l.get("layers") or [], drop_hidden, drop_empty, report)
        if drop_hidden and l.get("visible", True) is False:
            report["hidden_layers"].append(l.get("name", "")); continue
        if drop_empty and layer_empty(l):
            report["empty_layers"].append(l.get("name", "")); continue
        if "properties" in l and not l["properties"]:
            del l["properties"]; report["empty_properties"] += 1
        out.append(l)
    return out


def _tileset_count(ts, next_fg, used):
    if ts.get("tilecount"): return int(ts["tilecount"])
    fg = int(ts.get("firstgid", 1))
    if next_fg is not None: return max(1, int(next_fg) - fg)
    in_range = [g - fg + 1 for g in used if g >= fg]
    return max(in_range) if in_range else 1


def remap_gid(g, table):
    if not g: return 0
    loc, flags = g & MASK, g & FLAGS
    if loc == 0: return 0
    ng = table.get(loc, loc)
    return (ng | flags) if ng else 0


def remap_list(data, table):
    return [remap_gid(g, table) for g in data]


def apply_gid_table(m, table):
    def walk(layers):
        for l in layers or []:
            if l.get("type") == "group":
                walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                if "chunks" in l:
                    for c in l["chunks"]:
                        c["data"] = remap_list(c.get("data") or [], table)
                elif isinstance(l.get("data"), list):
                    l["data"] = remap_list(l["data"], table)
            elif l.get("type") == "objectgroup":
                for o in l.get("objects") or []:
                    if o.get("gid"):
                        o["gid"] = remap_gid(o["gid"], table)
    walk(m.get("layers") or [])


def reindex_firstgids(m, used=None):
    """Pack remaining tilesets to tight firstgids and remap every GID. Returns {old_firstgid: new_firstgid}."""
    sets = list(m.get("tilesets") or [])
    if not sets: return {}
    used = used if used is not None else used_gids(m.get("layers") or [])
    sets = sorted(sets, key=lambda t: int(t.get("firstgid", 1)))
    table, changes = {}, {}
    next_fg = 1
    new_sets = []
    for i, ts in enumerate(sets):
        ts = dict(ts)
        old_fg = int(ts.get("firstgid", 1))
        nxt = int(sets[i + 1].get("firstgid", old_fg)) if i + 1 < len(sets) else None
        count = _tileset_count(ts, nxt, used)
        ts["firstgid"] = next_fg
        if ts.get("tilecount") is None: ts["tilecount"] = count
        for loc in range(count):
            table[old_fg + loc] = next_fg + loc
        if old_fg != next_fg: changes[old_fg] = next_fg
        next_fg += count
        new_sets.append(ts)
    m["tilesets"] = new_sets
    if table: apply_gid_table(m, table)
    return changes


def clean(m, drop_hidden=True, drop_empty=True, drop_unused_tilesets=True, drop_empty_properties=True, reindex=True):
    m = map_diff.decode_map(m)  # deep copy + expand encoded tile data
    report = {"hidden_layers": [], "empty_layers": [], "unused_tilesets": [], "empty_properties": 0, "firstgid_remap": {}}
    m["layers"] = clean_layers(m.get("layers") or [], drop_hidden, drop_empty, report)
    if drop_empty_properties and "properties" in m and not m["properties"]:
        del m["properties"]; report["empty_properties"] += 1
    if drop_unused_tilesets and m.get("tilesets"):
        used = used_gids(m.get("layers") or []); keep = []
        sets = m["tilesets"]
        for i, ts in enumerate(sets):
            fg = ts.get("firstgid", 1); nxt = sets[i + 1]["firstgid"] if i + 1 < len(sets) else fg + ts.get("tilecount", 10 ** 9)
            if any(fg <= g < nxt for g in used): keep.append(ts)
            else: report["unused_tilesets"].append(ts.get("name") or ts.get("source") or f"tileset@{fg}")
        m["tilesets"] = keep
    if reindex:
        report["firstgid_remap"] = reindex_firstgids(m, used_gids(m.get("layers") or []))
    return m, report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Drop hidden, empty and unused parts of a Tiled JSON map; optionally reindex firstgids.")
    ap.add_argument("map"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--keep-hidden", action="store_true"); ap.add_argument("--keep-empty", action="store_true")
    ap.add_argument("--keep-unused-tilesets", action="store_true"); ap.add_argument("--keep-empty-properties", action="store_true")
    ap.add_argument("--keep-firstgids", action="store_true", help="leave firstgids and cell GIDs unchanged after dropping unused tilesets")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.map) and not a.in_place: sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    m, report = clean(json.load(open(a.map)), not a.keep_hidden, not a.keep_empty, not a.keep_unused_tilesets,
                      not a.keep_empty_properties, reindex=not a.keep_firstgids)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None), separators=(None if a.pretty else (",", ":")))
    print(f"dropped hidden {len(report['hidden_layers'])}, empty {len(report['empty_layers'])}, unused tilesets {len(report['unused_tilesets'])}, empty property lists {report['empty_properties']} -> {a.out}")
    for k in ("hidden_layers", "empty_layers", "unused_tilesets"):
        if report[k]: print(f"  {k}: " + ", ".join(report[k]))
    if report.get("firstgid_remap"):
        bits = ", ".join(f"{o}->{n}" for o, n in sorted(report["firstgid_remap"].items()))
        print(f"  firstgid remap: {bits}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
