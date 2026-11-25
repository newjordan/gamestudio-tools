#!/usr/bin/env python3
"""atlas-sort: sort frames in a TexturePacker-style atlas JSON by name, position
or size. The sheet image is not rewritten. Hash-object key order (Python 3.7+)
or the array order is updated. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out, atlas_json  # noqa: E402


def key_fn(by):
    if by == "name":
        return lambda it: it[0]
    if by == "x":
        return lambda it: (atlas_json.frame_xywh(it[1])[0], it[0])
    if by == "y":
        return lambda it: (atlas_json.frame_xywh(it[1])[1], it[0])
    if by == "width":
        return lambda it: (atlas_json.frame_xywh(it[1])[2], it[0])
    if by == "height":
        return lambda it: (atlas_json.frame_xywh(it[1])[3], it[0])
    if by == "area":
        return lambda it: (atlas_json.frame_xywh(it[1])[2] * atlas_json.frame_xywh(it[1])[3], it[0])
    raise SystemExit(f"unknown --by {by}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sort frames in an atlas JSON (image is not rewritten).")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--by", choices=("name", "x", "y", "width", "height", "area"), default="name")
    ap.add_argument("--desc", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    data, items, kind = atlas_json.load(a.input)
    items = sorted(items, key=key_fn(a.by), reverse=a.desc)
    meta = data.get("meta") or {}
    sw = (meta.get("size") or {}).get("w") or 1
    sh = (meta.get("size") or {}).get("h") or 1
    data, items, sw, sh = atlas_json._store(data, items, sw, sh)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    atlas_json.save(a.out, data)
    rec = {"out": a.out, "count": len(items), "by": a.by, "desc": bool(a.desc),
           "names": [n for n, _ in items]}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("sorted %d frame(s) by %s -> %s" % (len(items), a.by, a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
