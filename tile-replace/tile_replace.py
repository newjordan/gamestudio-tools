#!/usr/bin/env python3
"""tile-replace: remap GIDs in a Tiled JSON map from a JSON or CSV table (after tile-dedupe, or a manual swap list).
Flip flags are kept. Tile-layer cells and object `gid`s are rewritten. Unmapped GIDs are left alone unless
`--unmapped 0` (clear the cell) is set. Encoded tile data is decoded. Writes a new map; the input is never overwritten.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tilemap-stats"))
import map_diff, tilemap_stats  # noqa: E402

MASK = tilemap_stats.MASK
FLAGS = 0xE0000000


def load_table(path):
    """Return {old_gid: new_gid} (unflagged). Accepts JSON object, JSON list of {from,to}, or CSV with from,to."""
    low = path.lower()
    if low.endswith(".csv"):
        rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
        if not rows: sys.exit("remap CSV is empty")
        out = {}
        for r in rows:
            a = r.get("from") or r.get("old") or r.get("src") or r.get("gid")
            b = r.get("to") or r.get("new") or r.get("dst") or r.get("replace")
            if a is None or b is None: sys.exit("remap CSV needs from,to (or old,new) columns")
            out[int(a)] = int(b)
        return out
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict) and "remap" in data: data = data["remap"]
    if isinstance(data, dict):
        return {int(k): int(v) for k, v in data.items()}
    if isinstance(data, list):
        out = {}
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out[int(item[0])] = int(item[1])
            else:
                out[int(item.get("from", item.get("old")))] = int(item.get("to", item.get("new")))
        return out
    sys.exit("remap table must be a JSON object, a list of {from,to}, or a CSV")


def apply_gid(g, table, unmapped):
    if not g: return 0
    loc, flags = g & MASK, g & FLAGS
    if loc == 0: return 0
    if loc in table:
        ng = table[loc]
        return (ng | flags) if ng else 0
    if unmapped == "keep": return g
    return 0


def apply_list(data, table, unmapped):
    return [apply_gid(g, table, unmapped) for g in data]


def replace_map(m, table, unmapped="keep"):
    m = map_diff.decode_map(m)
    changed = 0

    def walk(layers):
        nonlocal changed
        for l in layers or []:
            typ = l.get("type")
            if typ == "group":
                walk(l.get("layers") or []); continue
            if typ == "tilelayer":
                if l.get("chunks"):
                    for c in l["chunks"]:
                        before = list(c.get("data") or [])
                        c["data"] = apply_list(before, table, unmapped)
                        changed += sum(a != b for a, b in zip(before, c["data"]))
                elif isinstance(l.get("data"), list):
                    before = list(l["data"])
                    l["data"] = apply_list(before, table, unmapped)
                    changed += sum(a != b for a, b in zip(before, l["data"]))
            elif typ == "objectgroup":
                for o in l.get("objects") or []:
                    if o.get("gid"):
                        ng = apply_gid(o["gid"], table, unmapped)
                        if ng != o["gid"]:
                            changed += 1; o["gid"] = ng
    walk(m.get("layers") or [])
    return m, {"remapped": len(table), "cells_changed": changed, "unmapped": unmapped}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Remap GIDs in a Tiled JSON map from a JSON or CSV table.")
    ap.add_argument("map"); ap.add_argument("--remap", required=True, help="JSON object/list or CSV with from,to")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--unmapped", choices=("keep", "0"), default="keep", help="what to do with GIDs not in the table")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.map) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    table = load_table(a.remap)
    if not table: sys.exit("remap table is empty")
    m, rec = replace_map(json.load(open(a.map, encoding="utf-8")), table, a.unmapped)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None), separators=(None if a.pretty else (",", ":")))
    rec["out"] = a.out
    print(f"{rec['cells_changed']} cell(s) changed, {rec['remapped']} mapping(s) -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
