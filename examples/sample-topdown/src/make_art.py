#!/usr/bin/env python3
"""Draw the raw, unprocessed pixel art for Ember Crypt with numpy + Pillow.

Everything here is a flat, un-outlined, un-shadowed source frame. gst does the
rest in build.sh: palette-apply (PICO-8), team-outline / palette-swap variants,
sprite-scale, sprite-outline-gen, sprite-shadow, sprite-angles, anim-from-folder,
atlas-pack and atlas-to-godot. Frames are named <clip>_<n>.png for
anim-from-folder's {clip}_{frame}.png pattern.

  sprites/  player, bat, wizard, boss (24 px, scaled 2x by gst), orb, coin,
            heart, key, slash (one arc; gst bakes 8 angles)
  props/    stairs and a rune tile (floor and wall tiles come from tex-gen)
  ui/       panel.png (nine-slice source, 24 px with a 6 px border)
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

PAL = {
    "k": (0, 0, 0), "n": (29, 43, 83), "p": (126, 37, 83), "g": (0, 135, 81),
    "b": (171, 82, 54), "d": (95, 87, 79), "l": (194, 195, 199), "w": (255, 241, 232),
    "r": (255, 0, 77), "o": (255, 163, 0), "y": (255, 236, 39), "G": (0, 228, 54),
    "B": (41, 173, 255), "v": (131, 118, 156), "P": (255, 119, 168), "s": (255, 204, 170),
}


def canvas(w, h):
    return np.zeros((h, w, 4), np.uint8)


def put(a, x, y, c):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x] = PAL[c] + (255,)


def rect(a, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(a, x, y, c)


def disc(a, cx, cy, r, c):
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + 0.5:
                put(a, x, y, c)


def save(a, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a, "RGBA").save(path)


def player(direction, step):
    """16x16 knight: rows 2..13 used, rows 14-15 left for the contact shadow."""
    a = canvas(16, 16)
    leg = [(0, 0), (1, -1), (0, 0), (-1, 1)][step % 4]
    rect(a, 5, 11, 6, 13 + min(0, leg[0]), "n")       # legs
    rect(a, 9, 11, 10, 13 + min(0, leg[1]), "n")
    rect(a, 4, 6, 11, 11, "B")                        # tunic
    rect(a, 4, 9, 11, 9, "b")                         # belt
    rect(a, 4, 2, 11, 6, "l")                         # helmet
    put(a, 7, 1, "r"); put(a, 8, 1, "r")              # plume
    if direction == "down":
        rect(a, 5, 4, 10, 5, "s"); put(a, 6, 4, "k"); put(a, 9, 4, "k")
    elif direction == "up":
        rect(a, 5, 4, 10, 5, "d")
    else:  # side, facing right; left is a runtime flip_h
        rect(a, 8, 4, 11, 5, "s"); put(a, 10, 4, "k")
        rect(a, 3, 7, 3, 10, "d")                     # shield edge
    arm = [0, 1, 0, -1][step % 4]
    put(a, 3, 8 + arm, "s"); put(a, 12, 8 - arm, "s")
    return a


def bat(frame):
    a = canvas(16, 16)
    up = frame % 2 == 0
    disc(a, 8, 7, 3, "p")
    put(a, 7, 6, "r"); put(a, 9, 6, "r")
    wing_y = 4 if up else 8
    for i in range(4):
        put(a, 4 - i, wing_y + (i // 2 if not up else -i // 2) + 2, "v")
        put(a, 12 + i, wing_y + (i // 2 if not up else -i // 2) + 2, "v")
    rect(a, 3, 6, 4, 8, "v"); rect(a, 12, 6, 13, 8, "v")
    if frame in (1, 2):
        put(a, 8, 11, "p")
    return a


def wizard(clip, frame):
    a = canvas(16, 16)
    rect(a, 4, 7, 11, 13, "g")                        # robe
    rect(a, 5, 13, 10, 13, "n")
    rect(a, 5, 4, 10, 7, "s"); put(a, 6, 5, "k"); put(a, 9, 5, "k")
    rect(a, 6, 8, 9, 10, "w")                         # beard
    for i in range(4):                                # hat
        rect(a, 4 + i, 4 - i, 11 - i, 4 - i, "g")
    put(a, 8, 0, "y")
    glow = "y" if clip == "cast" and frame == 1 else "o"
    rect(a, 12, 5, 12, 13, "b")                       # staff
    put(a, 12, 4, glow); put(a, 13, 4, glow if clip == "cast" else "o")
    if clip == "cast":
        put(a, 13, 3, "y"); put(a, 11, 3, glow)
    if clip == "idle" and frame == 1:
        rect(a, 4, 13, 11, 13, "g")
    return a


def boss(clip, frame):
    """24x24 stone golem; gst scales it 2x to 48x48."""
    a = canvas(24, 24)
    rect(a, 5, 6, 18, 18, "d")
    rect(a, 7, 2, 16, 7, "l")                         # head
    eye = "r" if clip == "charge" else "o"
    rect(a, 9, 4, 10, 5, eye); rect(a, 13, 4, 14, 5, eye)
    sh = 1 if frame % 2 else 0
    rect(a, 2, 8 + sh, 4, 15 + sh, "l"); rect(a, 19, 8 - sh, 21, 15 - sh, "l")   # arms
    rect(a, 7, 19, 10, 21 - sh, "d"); rect(a, 13, 19, 16, 21 - (1 - sh), "d")    # legs
    rect(a, 9, 10, 14, 13, "b"); put(a, 11, 11, "o"); put(a, 12, 12, "o")        # core
    return a


def orb(frame):
    a = canvas(8, 8)
    disc(a, 3.5, 3.5, 2.5, "P" if frame else "r")
    put(a, 3, 2, "w")
    return a


def coin(frame):
    a = canvas(12, 12)
    width = [4, 3, 1, 3][frame]
    for y in range(2, 10):
        for x in range(6 - width, 6 + width):
            put(a, x, y, "y")
    if width > 1:
        rect(a, 5, 4, 5, 7, "o")
    return a


def heart():
    a = canvas(12, 12)
    disc(a, 4, 4, 2, "r"); disc(a, 7, 4, 2, "r")
    for y in range(4, 10):
        for x in range(2 + (y - 4), 10 - (y - 4)):
            put(a, x, y, "r")
    put(a, 3, 3, "w")
    return a


def key():
    a = canvas(12, 12)
    disc(a, 4, 4, 2, "y"); put(a, 4, 4, "k")
    rect(a, 5, 4, 10, 5, "y"); rect(a, 8, 6, 8, 7, "y"); rect(a, 10, 6, 10, 7, "y")
    return a


def slash():
    """16x16 sword arc pointing right (angle 0); sprite-angles makes the other 7."""
    a = canvas(16, 16)
    for t in np.linspace(-1.1, 1.1, 40):
        for r in (5.5, 6.5):
            put(a, int(round(8 + r * np.cos(t))), int(round(8 + r * np.sin(t))), "w")
    for t in np.linspace(-0.8, 0.8, 20):
        put(a, int(round(8 + 4.5 * np.cos(t))), int(round(8 + 4.5 * np.sin(t))), "B")
    return a


def stairs():
    a = canvas(16, 16)
    rect(a, 0, 0, 15, 15, "k")
    for i in range(4):
        rect(a, 1 + i * 2, 2 + i * 3, 14 - i * 2, 3 + i * 3, "l" if i % 2 == 0 else "d")
    return a


def rune():
    a = canvas(16, 16)
    rect(a, 0, 0, 15, 15, "n")
    for i in range(4, 12):
        put(a, i, i, "B"); put(a, 15 - i, i, "B")
    disc(a, 7.5, 7.5, 1.5, "w")
    return a


def panel():
    a = canvas(24, 24)
    rect(a, 0, 0, 23, 23, "k")
    rect(a, 1, 1, 22, 22, "o")
    rect(a, 2, 2, 21, 21, "b")
    rect(a, 3, 3, 20, 20, "n")
    for c in ((1, 1), (22, 1), (1, 22), (22, 22)):
        put(a, c[0], c[1], "y")
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", required=True)
    out = Path(ap.parse_args().out)
    s = out / "sprites"
    for d in ("down", "up", "side"):
        for i in range(4):
            save(player(d, i), s / f"player-walk-{d}_{i}.png")
        save(player(d, 0), s / f"player-idle-{d}_0.png")
    for i in range(4):
        save(bat(i), s / f"bat-fly_{i}.png")
    for clip in ("idle", "cast"):
        for i in range(2):
            save(wizard(clip, i), s / f"wizard-{clip}_{i}.png")
    for clip in ("walk", "charge"):
        for i in range(2):
            save(boss(clip, i), out / "boss" / f"boss-{clip}_{i}.png")
    for i in range(2):
        save(orb(i), s / f"orb-spin_{i}.png")
    for i in range(4):
        save(coin(i), out / "pickups" / f"coin-spin_{i}.png")
    save(heart(), out / "pickups" / "heart-idle_0.png")
    save(key(), out / "pickups" / "key-idle_0.png")
    save(slash(), out / "slash.png")
    save(stairs(), out / "props" / "p02_stairs.png")
    save(rune(), out / "props" / "p03_rune.png")
    save(panel(), out / "ui" / "panel.png")
    print(f"raw art -> {out}")


if __name__ == "__main__":
    main()
