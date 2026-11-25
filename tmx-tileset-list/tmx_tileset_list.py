#!/usr/bin/env python3
"""tmx-tileset-list: list tilesets referenced by a Tiled JSON map (name,
firstgid, image or source, tilecount, columns, and how many unique local ids
are used on tile layers). External .tsx / .tsj tilesets are resolved next to
the map. Optional JSON and CSV reports; `--fail-if-none` exits 1 when the map
has no tilesets. The file is not rewritten.
"""
from __future__ import annotations

import argparse, os, csv, json, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_diff  # noqa: E402

MASK = 0x1FFFFFFF


def used_local_ids(m):
    """Map firstgid -> set of local ids used on tile layers."""
    tilesets = m.get("tilesets") or []
    bounds = []
    for i, ts in enumerate(tilesets):
        fg = int(ts.get("firstgid") or 1)
        nxt = int(tilesets[i + 1].get("firstgid") or (fg + 10**9)) if i + 1 < len(tilesets) else 10**9
        bounds.append((fg, nxt, ts))
    used = defaultdict(set)

    def walk(layers):
        for l in layers or []:
            if l.get("type") == "group":
                walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                for g in l.get("data") or []:
                    raw = int(g) & MASK
                    if not raw:
                        continue
                    hit = None
                    for fg, nxt, ts in bounds:
                        if fg <= raw < nxt:
                            hit = (fg, ts)
                    if hit:
                        used[hit[0]].add(raw - hit[0])

    walk(m.get("layers") or [])
    return used


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="List tilesets in a Tiled JSON map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", help="optional CSV")
    ap.add_argument("--json")
    ap.add_argument("--fail-if-none", action="store_true")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    for dest in (a.out, a.json):
        if dest:
            safe_out.check(a.map, dest, a.in_place)

    data = json.load(open(a.map, encoding="utf-8"))
    if data.get("type") == "map":
        data = map_diff.decode_map(data)
    base = os.path.dirname(os.path.abspath(a.map))
    data = map_diff.resolve_map_tilesets(data, base)
    used = used_local_ids(data)
    rows = []
    for ts in data.get("tilesets") or []:
        fg = int(ts.get("firstgid") or 1)
        tilecount = ts.get("tilecount")
        local = sorted(used.get(fg) or [])
        rows.append({
            "name": ts.get("name") or "",
            "firstgid": fg,
            "source": ts.get("source") or "",
            "image": ts.get("image") or "",
            "tilecount": tilecount,
            "columns": ts.get("columns"),
            "used_local_ids": len(local),
            "unused": (int(tilecount) - len(local)) if tilecount is not None else None,
        })
    rec = {"map": a.map, "count": len(rows), "tilesets": rows}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        fields = ["name", "firstgid", "source", "image", "tilecount", "columns", "used_local_ids", "unused"]
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print("%d tileset(s) in %s" % (len(rows), a.map))
    if a.fail_if_none and not rows:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
