#!/usr/bin/env python3
"""tile-dedupe: find duplicate and empty tiles in a tileset sheet (optionally treating flips/rotations as
duplicates), write a compacted tileset and an index remap JSON (old -> new + transform), and optionally
rewrite a Tiled map to use the compact set. Frees atlas space and keeps hand-made tilesets tidy.
Transforms (8 of the dihedral group): none, flipx, flipy, rot90ccw, rot180, rot90cw, transpose, antitranspose.
"""
import os
import argparse, json
import numpy as np
from PIL import Image
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

XF = {
    "none": lambda a: a, "flipx": lambda a: a[:, ::-1], "flipy": lambda a: a[::-1], "rot180": lambda a: a[::-1, ::-1],
    "rot90ccw": lambda a: np.rot90(a, 1), "rot90cw": lambda a: np.rot90(a, 3), "transpose": lambda a: a.transpose(1, 0, 2),
    "antitranspose": lambda a: np.rot90(a, 2).transpose(1, 0, 2),
}
# Tiled GID flag bits (H=0x80000000, V=0x40000000, D=0x20000000) for each transform that maps canonical -> variant
TILED = {"none": 0, "flipx": 0x80000000, "flipy": 0x40000000, "rot180": 0xC0000000, "transpose": 0x20000000,
         "rot90cw": 0xA0000000, "rot90ccw": 0x60000000, "antitranspose": 0xE0000000}


def tiles_of(img, t, margin=0, spacing=0):
    a = np.array(img.convert("RGBA"))
    cols = (a.shape[1] - margin + spacing) // (t[0] + spacing); rows = (a.shape[0] - margin + spacing) // (t[1] + spacing)
    out = []
    for r in range(rows):
        for c in range(cols):
            x, y = margin + c * (t[0] + spacing), margin + r * (t[1] + spacing)
            out.append(a[y:y + t[1], x:x + t[0]].copy())
    return out, cols, rows


def key(a):
    b = a.copy(); b[b[..., 3] == 0] = 0       # invisible pixels never make tiles "different"
    return b.tobytes(), b.shape


def dedupe(tiles, transforms=False):
    canon, remap, unique = {}, [], []
    for i, t in enumerate(tiles):
        if not (t[..., 3] > 0).any():
            remap.append({"old": i, "new": None, "xf": "none", "reason": "empty"}); continue
        found = None
        for name, f in (XF.items() if transforms else [("none", XF["none"])]):
            v = f(t)
            if v.shape == t.shape and key(v) in canon:     # non-square tiles skip rotations that change shape
                found = (canon[key(v)], name); break
        if found:
            remap.append({"old": i, "new": found[0], "xf": found[1], "reason": "duplicate"})
        else:
            canon[key(t)] = len(unique); unique.append(t); remap.append({"old": i, "new": len(unique) - 1, "xf": "none", "reason": "unique"})
    return unique, remap


def inverse_xf(name):
    """transform applied to the CANONICAL tile to obtain the duplicate. We stored f such that f(dup) == canon, so invert."""
    return {"rot90ccw": "rot90cw", "rot90cw": "rot90ccw"}.get(name, name)


def compact(unique, t, cols):
    rows = max(1, -(-len(unique) // cols))
    sheet = Image.new("RGBA", (cols * t[0], rows * t[1]))
    for i, u in enumerate(unique): sheet.paste(Image.fromarray(u, "RGBA"), ((i % cols) * t[0], (i // cols) * t[1]))
    return sheet


def remap_map(m, remap, empty_gid=0):
    table = {r["old"] + 1: (r["new"] + 1 if r["new"] is not None else empty_gid, TILED[inverse_xf(r["xf"])]) for r in remap}
    for l in m["layers"]:
        if l["type"] != "tilelayer": continue
        new = []
        for v in l["data"]:
            flags, gid = v & 0xE0000000, v & 0x1FFFFFFF
            if gid in table:
                ng, xf = table[gid]
                if ng == 0: new.append(0)
                elif flags and xf: raise SystemExit("a tile that already has flip flags became a transformed duplicate; run without --transforms for this map")
                else: new.append(ng | flags | xf)
            else: new.append(v)
        l["data"] = new
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dedupe tiles in a tileset.")
    ap.add_argument("tileset"); ap.add_argument("--tile", required=True); ap.add_argument("-o", "--out", required=True, help="basename (.png .json)")
    ap.add_argument("--margin", type=int, default=0); ap.add_argument("--spacing", type=int, default=0)
    ap.add_argument("--transforms", action="store_true", help="treat flips/rotations as duplicates")
    ap.add_argument("--columns", type=int, default=0); ap.add_argument("--map", help="Tiled map JSON to remap"); ap.add_argument("--map-out")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    for _cand in (a.out, a.out + '.png', a.out + '.json'):
        if os.path.abspath(_cand) == os.path.abspath(a.tileset) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    parts = a.tile.lower().replace(" ", "").split("x")
    try:
        if len(parts) == 1:
            tw = th = int(parts[0])
        elif len(parts) == 2:
            tw, th = int(parts[0]), int(parts[1])
        else:
            raise GstInputError("--tile needs WxH (for example 8x8)")
    except ValueError as e:
        raise GstInputError("--tile needs WxH (for example 8x8)") from e
    if tw < 1 or th < 1:
        raise GstInputError("--tile must be at least 1x1")
    t = (tw, th)
    tiles, cols, rows = tiles_of(gst_read.open_image(a.tileset), t, a.margin, a.spacing)
    if cols < 1 or rows < 1:
        raise GstInputError("tileset is smaller than the tile size")
    unique, remap = dedupe(tiles, a.transforms)
    compact(unique, t, a.columns or cols).save(a.out + ".png")
    json.dump({"tile": list(t), "original_count": len(tiles), "unique_count": len(unique), "remap": remap}, open(a.out + ".json", "w"), indent=1)
    if a.map:
        json.dump(remap_map(json.load(open(a.map)), remap), open(a.map_out or a.out + "_map.json", "w"))
    print(f"{len(tiles)} tiles -> {len(unique)} unique ({sum(r['reason'] == 'duplicate' for r in remap)} duplicate, {sum(r['reason'] == 'empty' for r in remap)} empty)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
