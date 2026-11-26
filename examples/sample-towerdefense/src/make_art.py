#!/usr/bin/env python3
"""Procedural pixel drawings for Reed Causeway.

gst tools do the packing, recolor, outline, shadow, stack and tileset steps.
This script only places the pixels those tools consume: the mill tile, tower
layers, creep frames, puff frames, the nine-slice panel, a 3x3 autotile
template, parallax bands and a tiny WFC example.
"""
import argparse, csv, os

from PIL import Image

GREEN = (106, 168, 79, 255)  # #6aa84f, the exact key sprite-recolor swaps
EYE = (26, 36, 28, 255)
FOOT = (61, 41, 20, 255)
BRUTE = (138, 75, 50, 255)
WOOD = (138, 106, 64, 255)
PATH = (196, 165, 116, 255)
ROOF = (90, 122, 138, 255)
GOLD = (230, 200, 74, 255)
CRYSTAL = (127, 211, 232, 255)
IRON = (90, 90, 98, 255)
REED = (63, 107, 58, 255)
DARK = (14, 22, 18, 255)


def new(w, h, color=(0, 0, 0, 0)):
    return Image.new("RGBA", (w, h), color)


def pix(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((x, y), c)


def rect(im, x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            pix(im, xx, yy, c)


def save(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)


def core_tile():
    im = new(16, 16, PATH)
    rect(im, 4, 8, 8, 6, WOOD)
    rect(im, 3, 5, 10, 4, ROOF)
    rect(im, 7, 10, 2, 4, DARK)
    pix(im, 6, 6, GOLD)
    pix(im, 9, 6, GOLD)
    return im


def grub(frame):
    im = new(16, 16)
    bob = (0, -1, 0, 1)[frame]
    rect(im, 4, 6 + bob, 8, 6, GREEN)
    rect(im, 5, 4 + bob, 6, 3, GREEN)
    pix(im, 6, 5 + bob, EYE)
    pix(im, 9, 5 + bob, EYE)
    foot_x = (5, 10) if frame % 2 == 0 else (4, 11)
    for x in foot_x:
        pix(im, x, 12 + bob, FOOT)
    return im


def brute(frame):
    im = new(16, 16)
    bob = (0, -1, 0, 1)[frame]
    rect(im, 3, 5 + bob, 10, 8, BRUTE)
    rect(im, 4, 3 + bob, 8, 3, BRUTE)
    pix(im, 6, 4 + bob, EYE)
    pix(im, 10, 4 + bob, EYE)
    pix(im, 5, 13 + bob, FOOT)
    pix(im, 10, 13 + bob, FOOT)
    if frame % 2:
        pix(im, 3, 8 + bob, WOOD)
        pix(im, 12, 8 + bob, WOOD)
    return im


def puff(frame):
    im = new(16, 16)
    radius = (1, 2, 3, 4)[frame]
    for y in range(16):
        for x in range(16):
            if (x - 8) ** 2 + (y - 8) ** 2 <= radius * radius:
                im.putpixel((x, y), GOLD)
    return im


def tower_layers(stem, head_color, head):
    base = new(16, 16)
    rect(base, 3, 11, 10, 3, WOOD)
    rect(base, 5, 9, 6, 2, (90, 70, 40, 255))
    top = new(16, 16)
    head(top, head_color)
    return base, top


def arrow_head(im, _color):
    rect(im, 7, 3, 2, 8, WOOD)
    rect(im, 4, 4, 8, 2, (224, 208, 176, 255))
    pix(im, 8, 2, GOLD)


def frost_head(im, color):
    rect(im, 6, 2, 4, 8, color)
    pix(im, 5, 4, color)
    pix(im, 10, 4, color)
    pix(im, 7, 1, (232, 248, 255, 255))


def mortar_head(im, color):
    rect(im, 4, 5, 8, 4, color)
    rect(im, 10, 4, 3, 2, DARK)
    pix(im, 6, 6, GOLD)


def panel():
    im = new(32, 32, (30, 40, 32, 255))
    rect(im, 0, 0, 32, 6, (58, 52, 40, 255))
    rect(im, 0, 26, 32, 6, (58, 52, 40, 255))
    rect(im, 0, 0, 6, 32, (58, 52, 40, 255))
    rect(im, 26, 0, 6, 32, (58, 52, 40, 255))
    rect(im, 6, 6, 20, 1, (90, 122, 90, 255))
    return im


def autotile():
    """3x3 template: grass border, path centre, mixed edges."""
    im = new(48, 48, (47, 107, 58, 255))
    rect(im, 16, 16, 16, 16, PATH)
    rect(im, 16, 0, 16, 16, (70, 120, 64, 255))
    rect(im, 16, 32, 16, 16, (40, 80, 48, 255))
    rect(im, 0, 16, 16, 16, (80, 110, 60, 255))
    rect(im, 32, 16, 16, 16, (55, 90, 50, 255))
    return im


def parallax(root):
    sky = new(320, 192, (20, 32, 43, 255))
    rect(sky, 0, 120, 320, 72, (28, 48, 64, 255))
    rect(sky, 0, 160, 320, 32, (36, 56, 72, 255))
    hills = new(320, 96)
    for x in range(320):
        hump = 40 + int(18 * ((x % 80) - 40) / 40.0) if (x // 80) % 2 == 0 else 55
        if hump < 20:
            hump = 20
        for y in range(hump, 96):
            pix(hills, x, y, (42, 64, 48, 255))
    reeds = new(320, 48)
    for x in range(4, 320, 7):
        h = 28 + (x * 3) % 16
        for y in range(48 - h, 46):
            pix(reeds, x, y, REED)
            if y % 4 == 0:
                pix(reeds, x + 1, y, (230, 200, 74, 255))
    save(sky, os.path.join(root, "parallax", "sky.png"))
    save(hills, os.path.join(root, "parallax", "hills.png"))
    save(reeds, os.path.join(root, "parallax", "reeds.png"))


def wfc_csv(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        csv.writer(fh).writerows([[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 1, 0], [1, 0, 0, 1]])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", required=True, help="work directory for the drawings")
    a = ap.parse_args()
    root = a.out
    save(core_tile(), os.path.join(root, "tiles", "t03_core.png"))
    for stem, color, head in (
        ("arrow", GOLD, arrow_head),
        ("frost", CRYSTAL, frost_head),
        ("mortar", IRON, mortar_head),
    ):
        base, top = tower_layers(stem, color, head)
        save(base, os.path.join(root, "towers", stem + ".base.png"))
        save(top, os.path.join(root, "towers", stem + ".head.png"))
    for i in range(4):
        save(grub(i), os.path.join(root, "creeps", "grub_%d.png" % i))
        save(brute(i), os.path.join(root, "creeps", "brute_%d.png" % i))
        save(puff(i), os.path.join(root, "puff", "puff_%d.png" % i))
    save(panel(), os.path.join(root, "ui", "panel.png"))
    save(autotile(), os.path.join(root, "autotile.png"))
    parallax(root)
    wfc_csv(os.path.join(root, "wfc.csv"))
    print("drawings -> %s" % root)


if __name__ == "__main__":
    main()
