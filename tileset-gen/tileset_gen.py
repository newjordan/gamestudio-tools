#!/usr/bin/env python3
"""tileset-gen: build a 47-tile "blob" (8-neighbour) autotile sheet from two terrain fills: an inner terrain A
(for example grass) and an outer terrain B (dirt, water, or transparent). Each tile is rendered from the tile's
neighbour mask: a missing side recedes by --border pixels, and an inner corner (both sides present, diagonal missing)
is notched. Optional 1px --edge-color line along the A/B boundary. A and B are PNGs (tiled across the tile) or #rrggbb.
Neighbour bits: N=1 NE=2 E=4 SE=8 S=16 SW=32 W=64 NW=128. A diagonal only counts when both adjacent sides are
present, which leaves exactly 47 distinct tiles. The JSON has a 256-entry `lookup` (raw neighbour mask -> tile
index) so game code can use raw masks. Sheet is 8 columns x 6 rows (slot 48 empty). Pixel-art oriented: hard edges, no rounding.
"""
import argparse, os, json, sys
import numpy as np
from PIL import Image

N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128
COLS = 8


def canon(m):
    keep = m & (N | E | S | W)
    for d, (a, b) in {NE: (N, E), SE: (S, E), SW: (S, W), NW: (N, W)}.items():
        if m & d and m & a and m & b: keep |= d
    return keep


CANON = sorted({canon(m) for m in range(256)})
INDEX = {m: i for i, m in enumerate(CANON)}
LOOKUP = [INDEX[canon(m)] for m in range(256)]


def mask_for(grid, x, y, solid=lambda v: v != 0):
    h, w = len(grid), len(grid[0]); m = 0
    for bit, dx, dy in ((N, 0, -1), (NE, 1, -1), (E, 1, 0), (SE, 1, 1), (S, 0, 1), (SW, -1, 1), (W, -1, 0), (NW, -1, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < w and 0 <= yy < h and solid(grid[yy][xx]): m |= bit
    return m


def region(t, b, m):
    r = np.ones((t, t), bool)
    if not m & N: r[:b, :] = False
    if not m & S: r[t - b:, :] = False
    if not m & W: r[:, :b] = False
    if not m & E: r[:, t - b:] = False
    if m & N and m & E and not m & NE: r[:b, t - b:] = False
    if m & S and m & E and not m & SE: r[t - b:, t - b:] = False
    if m & S and m & W and not m & SW: r[t - b:, :b] = False
    if m & N and m & W and not m & NW: r[:b, :b] = False
    return r


def fill(spec, t):
    if spec is None or spec == "none": return Image.new("RGBA", (t, t), (0, 0, 0, 0))
    if spec.startswith("#"): s = spec.lstrip("#"); return Image.new("RGBA", (t, t), tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
    src = Image.open(spec).convert("RGBA"); out = Image.new("RGBA", (t, t))
    for y in range(0, t, src.height):
        for x in range(0, t, src.width): out.paste(src, (x, y))
    return out


def render_tile(t, b, m, A, B, edge=None):
    r = region(t, b, m); a, bb = np.array(A), np.array(B)
    out = np.where(r[..., None], a, bb)
    if edge is not None:
        p = np.pad(r, 1, mode="edge"); inner = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        out[r & ~inner] = edge
    return out


def build(t=16, border=None, inner="#4a8f3c", outer="#8a6a3f", edge=None):
    b = border if border is not None else max(1, t // 4)
    if not 1 <= b <= t // 2: raise SystemExit("--border must be between 1 and tile/2")
    A, B = fill(inner, t), fill(outer, t); e = None
    if edge:
        s = edge.lstrip("#"); e = tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    rows = -(-len(CANON) // COLS); sheet = Image.new("RGBA", (COLS * t, rows * t), (0, 0, 0, 0))
    meta = {"tile": t, "border": b, "columns": COLS, "rows": rows, "count": len(CANON),
            "bits": {"N": N, "NE": NE, "E": E, "SE": SE, "S": S, "SW": SW, "W": W, "NW": NW}, "tiles": {}, "lookup": LOOKUP}
    for i, m in enumerate(CANON):
        x, y = (i % COLS) * t, (i // COLS) * t
        sheet.paste(Image.fromarray(render_tile(t, b, m, A, B, e), "RGBA"), (x, y)); meta["tiles"][str(i)] = {"mask": m, "x": x, "y": y}
    return sheet, meta


def main(argv=None):
    ap = argparse.ArgumentParser(description="47-tile blob autotile sheet from two terrain fills.")
    ap.add_argument("-o", "--out", required=True, help="basename: writes .png and .json"); ap.add_argument("--tile", type=int, default=16); ap.add_argument("--border", type=int)
    ap.add_argument("--inner", default="#4a8f3c"); ap.add_argument("--outer", default="#8a6a3f", help="PNG, #rrggbb, or none for transparent"); ap.add_argument("--edge-color")
    a = ap.parse_args(argv)
    sheet, meta = build(a.tile, a.border, a.inner, a.outer, a.edge_color)
    sheet.save(a.out + ".png"); json.dump(meta, open(a.out + ".json", "w"), indent=1)
    print(f"{meta['count']} tiles, {sheet.width}x{sheet.height} -> {a.out}.png/.json"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
