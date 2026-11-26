#!/usr/bin/env python3
"""Turn tileset-gen's 256-entry blob lookup into a map-auto-layer rule table.

One rule per raw 8-neighbour wall mask: the centre must be a wall (dungeon-gen
GID 2) and each neighbour must be a wall (2, or 0 for off-map, so the border
reads as solid rock) or floor (1). The placed GID is the blob tile index + 1
(the blob sheet is the map's first tileset). map-auto-layer --match gid does
the actual autotiling.
"""
import argparse, json

DIRS = [("n", 1), ("ne", 2), ("e", 4), ("se", 8), ("s", 16), ("sw", 32), ("w", 64), ("nw", 128)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("meta", help="tileset-gen JSON (bits + lookup)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--wall", type=int, default=2)
    ap.add_argument("--floor", type=int, default=1)
    a = ap.parse_args()
    meta = json.load(open(a.meta))
    bits = {k.lower(): v for k, v in meta["bits"].items()}
    assert all(bits[d] == b for d, b in DIRS), "unexpected tileset-gen bit layout"
    rules = []
    for mask in range(256):
        r = {"center": [a.wall], "gid": int(meta["lookup"][mask]) + 1}
        for d, b in DIRS:
            r[d] = [0, a.wall] if mask & b else [a.floor]
        rules.append(r)
    json.dump({"source": "dungeon", "name": "walls", "match": "gid", "rules": rules}, open(a.out, "w"))
    print(f"{len(rules)} blob rules -> {a.out}")


if __name__ == "__main__":
    main()
