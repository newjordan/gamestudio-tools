#!/usr/bin/env python3
"""Procedural pieces the kit's tex-gen does not draw: an asymmetric grass
edge (so H/V/diagonal flips are visible), four gem sparkle frames, a two-tile
door, a torch, and a UI panel for nine-slice. Writes one PNG per piece.

Authored for examples/sample-game-full. No downloaded or hand-drawn art.
"""
import argparse, math
from pathlib import Path
from PIL import Image, ImageDraw

OUT = (26, 26, 46, 255)


def edge():
    """Grass cap over dirt whose LEFT side is rounded off (flip H for right)."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([3, 4, 15, 15], fill=(138, 98, 52, 255))
    d.rectangle([5, 9, 6, 10], fill=(106, 69, 34, 255))
    d.rectangle([10, 12, 11, 13], fill=(106, 69, 34, 255))
    d.pieslice([0, 0, 10, 12], 180, 270, fill=(74, 170, 58, 255))
    d.rectangle([5, 0, 15, 4], fill=(74, 170, 58, 255))
    d.rectangle([0, 6, 3, 15], fill=(138, 98, 52, 255))
    for x in range(5, 16, 3):
        d.point((x, 5), fill=(46, 122, 40, 255))
    d.line([(0, 6), (0, 15)], fill=OUT)
    return im


def gem(t):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = (6, 4, 2, 4)[t]
    d.polygon([(8, 2), (8 + w, 7), (8, 14), (8 - w, 7)], fill=(60, 200, 240, 255), outline=OUT)
    if w > 2:
        d.line([(8 - w + 1, 7), (8 + w - 1, 7)], fill=(170, 240, 255, 255))
    sx = (11, 4, 12, 3)[t]
    d.point((sx, 3), fill=(255, 255, 255, 255))
    d.point((sx, 2), fill=(255, 255, 220, 255))
    return im


def door(top):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if top:
        d.pieslice([1, 1, 15, 20], 180, 360, fill=(110, 70, 40, 255), outline=OUT)
        d.rectangle([1, 10, 15, 15], fill=(110, 70, 40, 255))
        d.line([(8, 3), (8, 15)], fill=(80, 48, 26, 255))
    else:
        d.rectangle([1, 0, 15, 15], fill=(110, 70, 40, 255))
        d.line([(8, 0), (8, 15)], fill=(80, 48, 26, 255))
        d.rectangle([11, 6, 12, 8], fill=(240, 200, 60, 255))
        d.line([(1, 0), (1, 15)], fill=OUT); d.line([(15, 0), (15, 15)], fill=OUT)
    return im


def torch():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([7, 8, 8, 15], fill=(90, 60, 30, 255))
    d.ellipse([5, 2, 10, 9], fill=(250, 150, 40, 255))
    d.ellipse([6, 4, 9, 8], fill=(255, 230, 120, 255))
    return im


def panel():
    """24x24 UI frame: 6 px border, flat stretchable middle."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 23, 23], radius=5, fill=(30, 34, 64, 235), outline=(240, 200, 60, 255), width=2)
    d.rounded_rectangle([3, 3, 20, 20], radius=3, outline=(110, 120, 190, 255), width=1)
    for (x, y) in ((2, 2), (21, 2), (2, 21), (21, 21)):
        d.point((x, y), fill=(255, 240, 160, 255))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    edge().save(out / "t04_edge.png")
    for t in range(4):
        gem(t).save(out / f"t{5 + t:02d}_gem{t}.png")
    door(True).save(out / "t09_door_top.png")
    door(False).save(out / "t10_door_bottom.png")
    torch().save(out / "t11_torch.png")
    panel().save(out / "panel.png")
    print("wrote tile pieces to", out)


if __name__ == "__main__":
    main()
