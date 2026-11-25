#!/usr/bin/env python3
"""autotile-gen: build a 16-tile (4-bit edge bitmask) autotile sheet from one 3x3 "template" image.

Template: a 3x3 block of tiles. Top row = top-left corner, top edge, top-right corner; middle row = left edge,
fill, right edge; bottom row = bottom-left corner, bottom edge, bottom-right corner (the layout most
tileset artists already draw). Each output tile is assembled from four half-tile quadrants chosen by which
orthogonal neighbours (N, E, S, W) are present. Bitmask: N=1, E=2, S=4, W=8; tile index = mask, sheet is
4 columns x 4 rows. JSON lists mask -> index -> (x, y). Diagonal-aware 47-tile blob sets need an extra
inner-corner art slot and are not generated here.
"""
import os
import argparse, json
from PIL import Image
import sys

N, E, S, W = 1, 2, 4, 8


def quadrant_slot(v_present, h_present, vside, hside):
    """slot (col,row) in the 3x3 template for one quadrant. vside: 'top'/'bottom', hside: 'left'/'right'."""
    row = 1 if v_present else (0 if vside == "top" else 2)
    col = 1 if h_present else (0 if hside == "left" else 2)
    return col, row


def build_tile(template, t, mask):
    h = t // 2
    tile = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    for vside, hside in (("top", "left"), ("top", "right"), ("bottom", "left"), ("bottom", "right")):
        v = bool(mask & (N if vside == "top" else S))
        hh = bool(mask & (W if hside == "left" else E))
        col, row = quadrant_slot(v, hh, vside, hside)
        qx = 0 if hside == "left" else h
        qy = 0 if vside == "top" else h
        src = template.crop((col * t + qx, row * t + qy, col * t + qx + h, row * t + qy + h))
        tile.paste(src, (qx, qy))
    return tile


def build(template, t):
    if template.width != 3 * t or template.height != 3 * t:
        raise SystemExit(f"template must be 3x3 tiles ({3 * t}x{3 * t}); got {template.size}")
    if t % 2:
        raise SystemExit("tile size must be even")
    sheet = Image.new("RGBA", (4 * t, 4 * t), (0, 0, 0, 0))
    meta = {"tile": t, "columns": 4, "rows": 4, "bitmask": {"N": N, "E": E, "S": S, "W": W}, "tiles": {}}
    for mask in range(16):
        x, y = (mask % 4) * t, (mask // 4) * t
        sheet.paste(build_tile(template, t, mask), (x, y))
        meta["tiles"][str(mask)] = {"index": mask, "x": x, "y": y, "neighbours": [n for n, b in (("N", N), ("E", E), ("S", S), ("W", W)) if mask & b]}
    return sheet, meta


def mask_for(grid, x, y, solid=lambda v: v != 0):
    """neighbour bitmask of cell (x,y) in a 2D list; out-of-bounds counts as not present."""
    def at(cx, cy):
        return 0 <= cy < len(grid) and 0 <= cx < len(grid[0]) and solid(grid[cy][cx])
    return (N if at(x, y - 1) else 0) | (E if at(x + 1, y) else 0) | (S if at(x, y + 1) else 0) | (W if at(x - 1, y) else 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate a 16-tile autotile sheet from a 3x3 template.")
    ap.add_argument("template")
    ap.add_argument("--tile", type=int, required=True, help="tile size in px (template is 3x this)")
    ap.add_argument("-o", "--out", required=True, help="basename (.png + .json)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('template',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    sheet, meta = build(Image.open(a.template).convert("RGBA"), a.tile)
    sheet.save(a.out + ".png")
    json.dump(meta, open(a.out + ".json", "w"), indent=1)
    print(f"wrote {a.out}.png (4x4 tiles of {a.tile}px) and {a.out}.json")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
