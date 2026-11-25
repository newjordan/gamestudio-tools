#!/usr/bin/env python3
"""Paste a single tile image into a tileset sheet at a given index (showcase helper)."""
import argparse, sys
from PIL import Image


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stamp a tile into a sheet slot")
    ap.add_argument("sheet")
    ap.add_argument("tile")
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--columns", type=int, default=8)
    ap.add_argument("--tile-size", type=int, default=16)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    sheet = Image.open(a.sheet).convert("RGBA")
    tile = Image.open(a.tile).convert("RGBA")
    t = a.tile_size
    if tile.size != (t, t):
        tile = tile.resize((t, t), Image.Resampling.NEAREST)
    x, y = (a.index % a.columns) * t, (a.index // a.columns) * t
    if x + t > sheet.width or y + t > sheet.height:
        sys.exit(f"index {a.index} does not fit on {sheet.size} with tile {t} and {a.columns} columns")
    sheet.paste(tile, (x, y))
    sheet.save(a.out)
    print(f"stamped {a.tile} at index {a.index} ({x},{y}) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
