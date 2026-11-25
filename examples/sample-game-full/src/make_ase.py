#!/usr/bin/env python3
"""Draw the player and enemy procedurally and write them as binary Aseprite
files (32-bit RGBA, one layer, zlib cels, tags with directions).

Authored for examples/sample-game-full. No downloaded or hand-drawn art.
"""
import argparse, struct, zlib
from pathlib import Path
from PIL import Image, ImageDraw

OUTLINE = (26, 26, 46, 255)


def pstr(s):
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


def chunk(kind, payload):
    return struct.pack("<IH", 6 + len(payload), kind) + payload


def write_ase(path, frames, durations, tags, layer="body"):
    """frames: list of RGBA PIL images (same size). tags: list of
    (name, from, to, direction 0 fwd/1 rev/2 pingpong, repeat)."""
    w, h = frames[0].size
    out = []
    for i, im in enumerate(frames):
        chunks = []
        if i == 0:
            lp = struct.pack("<HHHHHHB", 1, 0, 0, 0, 0, 0, 255) + b"\x00\x00\x00" + pstr(layer)
            chunks.append(chunk(0x2004, lp))
            if tags:
                body = struct.pack("<H", len(tags)) + b"\x00" * 8
                for name, a, b, d, rep in tags:
                    body += struct.pack("<HHBH", a, b, d, rep) + b"\x00" * 6 + b"\xff\xff\xff" + b"\x00" + pstr(name)
                chunks.append(chunk(0x2018, body))
        raw = im.convert("RGBA").tobytes()
        cp = struct.pack("<HhhBH", 0, 0, 0, 255, 2) + b"\x00" * 7 + struct.pack("<HH", w, h) + zlib.compress(raw, 9)
        chunks.append(chunk(0x2005, cp))
        data = b"".join(chunks)
        out.append(struct.pack("<IHHH2sI", 16 + len(data), 0xF1FA, len(chunks), durations[i], b"\x00\x00", len(chunks)) + data)
    body = b"".join(out)
    header = bytearray(128)
    struct.pack_into("<IHHHHHIH", header, 0, 128 + len(body), 0xA5E0, len(frames), w, h, 32, 1, durations[0])
    struct.pack_into("<H", header, 32, 256)
    struct.pack_into("<BB", header, 34, 1, 1)  # pixel ratio 1:1
    Path(path).write_bytes(bytes(header) + body)


def player_frame(kind, t):
    """16x24 hero: helmet, visor, torso, legs. kind in idle/run/jump/fall/hurt."""
    im = Image.new("RGBA", (16, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bob = 0
    if kind == "idle":
        bob = t % 2
    elif kind == "run":
        bob = (0, 1, 0, 1)[t]
    body = (64, 132, 220, 255) if kind != "hurt" else (230, 80, 80, 255)
    skin = (246, 210, 170, 255)
    # legs
    if kind == "run":
        lx = ((3, 9), (5, 8), (9, 3), (8, 5))[t]
        d.rectangle([lx[0], 18, lx[0] + 2, 23], fill=(40, 40, 70, 255))
        d.rectangle([lx[1], 18, lx[1] + 2, 23], fill=(30, 30, 55, 255))
    elif kind in ("jump", "fall"):
        d.rectangle([4, 17, 6, 21], fill=(40, 40, 70, 255))
        d.rectangle([9, 18 if kind == "jump" else 17, 11, 22], fill=(30, 30, 55, 255))
    else:
        d.rectangle([4, 18, 6, 23], fill=(40, 40, 70, 255))
        d.rectangle([9, 18, 11, 23], fill=(30, 30, 55, 255))
    # torso
    d.rectangle([3, 10 + bob, 12, 18 + bob], fill=body)
    d.rectangle([3, 15 + bob, 12, 16 + bob], fill=(240, 200, 60, 255))  # belt
    # arms
    if kind == "jump":
        d.rectangle([1, 7, 2, 12], fill=skin); d.rectangle([13, 7, 14, 12], fill=skin)
    else:
        sw = (0, 1, 0, -1)[t % 4] if kind == "run" else 0
        d.rectangle([1, 11 + bob + sw, 2, 15 + bob + sw], fill=skin)
        d.rectangle([13, 11 + bob - sw, 14, 15 + bob - sw], fill=skin)
    # head / helmet
    d.rectangle([4, 2 + bob, 11, 9 + bob], fill=skin)
    d.rectangle([3, 1 + bob, 12, 4 + bob], fill=(220, 60, 60, 255))
    d.rectangle([8, 5 + bob, 10, 6 + bob], fill=(20, 20, 30, 255))  # eye (faces right)
    return outline(im)


def enemy_frame(kind, t):
    """16x16 slime that squashes while it walks."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    squash = (0, 1, 2, 1)[t] if kind == "walk" else 3
    col = (225, 232, 225, 255) if kind == "walk" else (255, 255, 255, 255)  # pale: tinted per kind from data/enemies.csv
    top = 4 + squash
    d.ellipse([1 - squash // 2, top, 14 + squash // 2, 15], fill=col)
    d.rectangle([1, 12, 14, 15], fill=col)
    d.rectangle([4, top + 3, 5, top + 5], fill=(20, 30, 20, 255))
    d.rectangle([10, top + 3, 11, top + 5], fill=(20, 30, 20, 255))
    d.point((3, top + 1), fill=(255, 255, 255, 255))
    return outline(im)


def outline(im):
    """1 px outline around opaque pixels (procedural, keeps size)."""
    a = im.split()[3]
    px = a.load()
    w, h = im.size
    out = im.copy()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] == 0 and any(0 <= x + dx < w and 0 <= y + dy < h and px[x + dx, y + dy] > 0
                                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                op[x, y] = OUTLINE
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--outdir", required=True)
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    frames = [player_frame("idle", 0), player_frame("idle", 1)]
    frames += [player_frame("run", t) for t in range(4)]
    frames += [player_frame("jump", 0), player_frame("fall", 0), player_frame("hurt", 0)]
    durs = [400, 400, 90, 90, 90, 90, 100, 100, 120]
    tags = [("idle", 0, 1, 2, 0), ("run", 2, 5, 0, 0), ("jump", 6, 6, 0, 0),
            ("fall", 7, 7, 0, 0), ("hurt", 8, 8, 0, 0)]
    write_ase(out / "player.aseprite", frames, durs, tags)
    ef = [enemy_frame("walk", t) for t in range(4)] + [enemy_frame("hurt", 0)]
    write_ase(out / "slime.aseprite", ef, [140, 140, 140, 140, 150],
              [("walk", 0, 3, 2, 0), ("hurt", 4, 4, 0, 0)])
    print("wrote", out / "player.aseprite", out / "slime.aseprite")


if __name__ == "__main__":
    main()
