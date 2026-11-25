#!/usr/bin/env python3
"""tmx-gid-usage: count GID usage in a Tiled JSON map. Reports per GID (tileset
name, local id, flip-flag counts) and unused tiles in each tileset. Encoded
layers are decoded first. Optional `--fail-on-unused-tileset` exits 1 when a
tileset has no used tiles. The input is never overwritten unless `--in-place`
(only relevant for `--json` / `-o`).
"""
import argparse, os, csv, json, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLIP_H, FLIP_V, FLIP_D = 0x80000000, 0x40000000, 0x20000000


def tileset_of(gid, tilesets):
    raw = gid & MASK
    if raw == 0:
        return None, 0, None
    hit = None
    for ts in tilesets:
        fg = int(ts.get("firstgid") or 1)
        if raw >= fg:
            if hit is None or fg >= int(hit.get("firstgid") or 1):
                hit = ts
    if hit is None:
        return None, raw, None
    fg = int(hit.get("firstgid") or 1)
    return hit, raw, raw - fg


def walk_layers(layers, acc, layer_counts):
    for l in layers or []:
        typ = l.get("type")
        if typ == "group":
            walk_layers(l.get("layers") or [], acc, layer_counts)
        elif typ == "tilelayer":
            name = l.get("name") or ""
            data = l.get("data") or []
            for g in data:
                g = int(g)
                raw = g & MASK
                if raw == 0:
                    continue
                acc[g] += 1
                layer_counts[name][raw] += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Count GID usage in a Tiled JSON map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", help="optional CSV of per-GID counts")
    ap.add_argument("--json")
    ap.add_argument("--fail-on-unused-tileset", action="store_true",
                    help="exit 1 if a tileset has no used tiles")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    dests = [p for p in (a.out, a.json) if p]
    for d in dests:
        safe_out.check(a.map, d, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    tilesets = m.get("tilesets") or []
    acc, layer_counts = Counter(), defaultdict(Counter)
    walk_layers(m.get("layers") or [], acc, layer_counts)
    # aggregate by raw GID (flags stripped) plus flip counts
    by_raw = defaultdict(lambda: {"count": 0, "flip_h": 0, "flip_v": 0, "flip_d": 0})
    for g, n in acc.items():
        raw_g = g & MASK
        rec = by_raw[raw_g]
        rec["count"] += n
        if g & FLIP_H:
            rec["flip_h"] += n
        if g & FLIP_V:
            rec["flip_v"] += n
        if g & FLIP_D:
            rec["flip_d"] += n
    gids = []
    used_local = defaultdict(set)
    for raw_g in sorted(by_raw):
        ts, _r, local = tileset_of(raw_g, tilesets)
        name = (ts or {}).get("name") or ""
        if ts is not None and local is not None:
            used_local[id(ts)].add(local)
        row = {"gid": raw_g, "local_id": local, "tileset": name, **by_raw[raw_g]}
        gids.append(row)
    unused_tilesets = []
    unused_tiles = []
    for ts in tilesets:
        count = int(ts.get("tilecount") or 0)
        used = used_local.get(id(ts), set())
        name = ts.get("name") or ""
        missing = [i for i in range(count) if i not in used]
        if count and not used:
            unused_tilesets.append(name or f"firstgid={ts.get('firstgid')}")
        unused_tiles.append({"tileset": name, "firstgid": ts.get("firstgid"),
                             "tilecount": count, "used": len(used), "unused": missing})
    rec = {"gids": gids, "layers": {k: dict(v) for k, v in layer_counts.items()},
           "tilesets": unused_tiles, "unused_tilesets": unused_tilesets,
           "used_gids": len(gids), "placed": int(sum(r["count"] for r in gids))}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["gid", "local_id", "tileset", "count", "flip_h", "flip_v", "flip_d"])
            w.writeheader()
            w.writerows(gids)
    print(f"{rec['placed']} placed tile(s), {rec['used_gids']} unique GID(s), "
          f"{len(unused_tilesets)} unused tileset(s)")
    if a.fail_on_unused_tileset and unused_tilesets:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
