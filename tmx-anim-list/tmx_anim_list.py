#!/usr/bin/env python3
"""tmx-anim-list: list tile animations in a Tiled tileset or map
(`tiles[].animation = [{tileid, duration}, ...]`). External .tsx / .tsj
tilesets are resolved next to the file. Writes optional JSON / CSV. The
input is not rewritten; report paths may not overwrite it unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-anim-gif"))
import safe_out, tile_anim_gif  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="List Tiled tile animations from a tileset or map.")
    ap.add_argument("input", help="Tiled JSON map or tileset (JSON/TSX/TSJ)")
    ap.add_argument("--json")
    ap.add_argument("-o", "--out", help="CSV path")
    ap.add_argument("--fail-if-none", action="store_true")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    for dest in (a.json, a.out):
        if dest:
            safe_out.check(a.input, dest, a.in_place)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
    import map_diff
    inp = a.input
    if inp.lower().endswith((".tsx", ".xml")):
        data = map_diff.load_tsx(inp)
    else:
        data = json.load(open(inp, encoding="utf-8"))
        if data.get("type") == "map":
            data = map_diff.decode_map(data)
    base = os.path.dirname(os.path.abspath(inp))
    # load_tilesets skips tilesets without an image; animations can live on collection
    # tilesets too, so walk tilesets ourselves and still resolve externals.
    if data.get("type") == "map":
        sets = data.get("tilesets") or []
    else:
        sets = [data]
    rows = []
    for ts in sets:
        ts = map_diff.resolve_tileset(ts, base)
        name = ts.get("name") or "tileset"
        firstgid = int(ts.get("firstgid") or 1)
        tiles = ts.get("tiles") or []
        for t in tiles:
            anim = t.get("animation") or []
            if not anim:
                continue
            frames = [{"tileid": int(f["tileid"]), "duration": int(f["duration"])} for f in anim]
            total = sum(f["duration"] for f in frames)
            lid = int(t["id"])
            rows.append({
                "tileset": name,
                "local_id": lid,
                "gid": firstgid + lid,
                "frames": len(frames),
                "duration_ms": total,
                "animation": frames,
            })
    rec = {"count": len(rows), "animations": rows, "input": a.input}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        fields = ["tileset", "local_id", "gid", "frames", "duration_ms"]
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print("%d tile animation(s) in %s" % (len(rows), a.input))
    if a.fail_if_none and not rows:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
