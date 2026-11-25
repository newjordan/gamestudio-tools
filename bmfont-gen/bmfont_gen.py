#!/usr/bin/env python3
"""bmfont-gen: bake a bitmap font (BMFont text format .fnt + PNG atlas) from a TrueType/OpenType font.

For pixel/retro UIs, engines without runtime font rendering, and consistent text across platforms.
Output loads in Godot (BMFont import), Unity (TextMesh Pro via BMFont), Phaser, libGDX, Cocos, etc.
YOU must have the right to embed the font: use OFL/Apache/public-domain fonts only for open-licence projects.
`--font default` uses the font bundled with Pillow (Aileron; understood to be CC0, but verify against Pillow's docs before shipping it).
Format reference: AngelCode BMFont text format (publicly documented).
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont
import os, sys


def load_font(spec, size):
    if spec == "default":
        return ImageFont.load_default(size)
    return ImageFont.truetype(spec, size)


def bake(font, chars, padding=1, aa=True, max_w=512):
    asc, desc = font.getmetrics()
    glyphs = []
    for ch in chars:
        l, t, r, b = font.getbbox(ch, anchor="ls")           # relative to baseline origin
        w, h = max(r - l, 0), max(b - t, 0)
        im = Image.new("L", (max(w, 1), max(h, 1)), 0)
        if w and h:
            d = ImageDraw.Draw(im)
            d.fontmode = "L" if aa else "1"
            d.text((-l, -t), ch, 255, font=font, anchor="ls")
        if im.getbbox() is None:            # whitespace / empty glyph: advance only
            w = h = 0
            im = Image.new("L", (1, 1), 0)
        glyphs.append({"id": ord(ch), "ch": ch, "img": im, "w": w, "h": h, "xoff": l, "yoff": asc + t, "xadv": round(font.getlength(ch))})
    x = y = padding
    row_h = 0
    for g in sorted(glyphs, key=lambda g: -g["h"]):
        if x + g["w"] + padding > max_w:
            x, y, row_h = padding, y + row_h + padding, 0
        g["x"], g["y"] = x, y
        x += g["w"] + padding
        row_h = max(row_h, g["h"])
    H = 1
    while H < y + row_h + padding: H *= 2
    atlas = Image.new("RGBA", (max_w, H), (255, 255, 255, 0))
    for g in glyphs:
        if g["w"] and g["h"]:
            tile = Image.new("RGBA", g["img"].size, (255, 255, 255, 0)); tile.putalpha(g["img"])
            atlas.paste(tile, (g["x"], g["y"]))
    return atlas, glyphs, asc + desc, asc


def fnt_text(face, size, line_h, base, atlas, glyphs, png_name, padding):
    out = [f'info face="{face}" size={size} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing={padding},{padding}',
           f"common lineHeight={line_h} base={base} scaleW={atlas.width} scaleH={atlas.height} pages=1 packed=0",
           f'page id=0 file="{png_name}"', f"chars count={len(glyphs)}"]
    for g in sorted(glyphs, key=lambda g: g["id"]):
        out.append(f"char id={g['id']} x={g.get('x', 0)} y={g.get('y', 0)} width={g['w']} height={g['h']} "
                   f"xoffset={g['xoff']} yoffset={g['yoff']} xadvance={g['xadv']} page=0 chnl=15")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake a BMFont bitmap font.")
    ap.add_argument("--font", required=True, help="path to .ttf/.otf, or 'default'")
    ap.add_argument("--size", type=int, default=16)
    ap.add_argument("--chars", help="characters to include (default printable ASCII)")
    ap.add_argument("--charfile", help="UTF-8 file whose characters to include (e.g. all your localised strings)")
    ap.add_argument("--no-aa", action="store_true", help="1-bit glyphs for crisp pixel fonts")
    ap.add_argument("--padding", type=int, default=1)
    ap.add_argument("-o", "--out", required=True, help="basename; writes .fnt and .png")
    a = ap.parse_args(argv)
    chars = a.chars or "".join(chr(c) for c in range(32, 127))
    if a.charfile:
        chars += open(a.charfile, encoding="utf-8").read()
    chars = "".join(dict.fromkeys(c for c in chars if c.isprintable()))
    font = load_font(a.font, a.size)
    atlas, glyphs, line_h, base = bake(font, chars, a.padding, not a.no_aa)
    atlas.save(a.out + ".png")
    face = os.path.splitext(os.path.basename(a.font))[0]
    open(a.out + ".fnt", "w", encoding="utf-8").write(fnt_text(face, a.size, line_h, base, atlas, glyphs, os.path.basename(a.out) + ".png", a.padding))
    print(f"baked {len(glyphs)} glyphs at {a.size}px -> {a.out}.fnt/.png ({atlas.width}x{atlas.height})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
