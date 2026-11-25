#!/usr/bin/env python3
"""contact-sheet: pack a folder of images into a labelled contact sheet PNG (fixed cell size, optional captions
from file stems, columns, padding and background). Images are fitted with nearest-neighbour (pixel art) or bilinear
scaling, never cropped except by --crop-empty transparent edges. The input files are never overwritten.
"""
import argparse, os, sys

from PIL import Image, ImageDraw, ImageFont


EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga"}


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p) if os.path.splitext(f)[1].lower() in EXTS))
        elif os.path.splitext(p)[1].lower() in EXTS:
            out.append(p)
        else:
            raise SystemExit(f"not an image or folder: {p}")
    return out


def crop_empty(im):
    a = im.convert("RGBA")
    bbox = a.getbbox()
    return a.crop(bbox) if bbox else a


def fit(im, cell, nearest):
    im = im.convert("RGBA")
    if im.width == 0 or im.height == 0: return Image.new("RGBA", cell, (0, 0, 0, 0))
    scale = min(cell[0] / im.width, cell[1] / im.height, 1) if False else min(cell[0] / im.width, cell[1] / im.height)
    if scale <= 0: return Image.new("RGBA", cell, (0, 0, 0, 0))
    w, h = max(1, int(round(im.width * scale))), max(1, int(round(im.height * scale)))
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.BILINEAR
    return im.resize((w, h), resample)


def parse_color(s):
    bg = s.lstrip("#")
    if len(bg) == 6: bg += "ff"
    return tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4, 6))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a labelled contact sheet from a folder of images.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cell", default="128x128", help="cell size WxH")
    ap.add_argument("--columns", type=int)
    ap.add_argument("--pad", type=int, default=8)
    ap.add_argument("--caption-h", type=int, default=14)
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--bg", default="#202020")
    ap.add_argument("--bilinear", action="store_true")
    ap.add_argument("--crop-empty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) in {os.path.abspath(p) for p in a.inputs}:
        sys.exit("refusing to overwrite an input; pick a different -o or pass --in-place")
    try:
        cw, ch = (int(x) for x in a.cell.lower().split("x"))
    except Exception:
        sys.exit("--cell must be WxH")
    files = collect(a.inputs)
    if not files: sys.exit("no images found")
    cap_h = 0 if a.no_captions else max(0, a.caption_h)
    cols = a.columns or max(1, int(len(files) ** 0.5 + 0.99))
    rows = -(-len(files) // cols)
    pad = max(0, a.pad)
    W = cols * cw + (cols + 1) * pad
    H = rows * (ch + cap_h) + (rows + 1) * pad
    sheet = Image.new("RGBA", (W, H), parse_color(a.bg))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, path in enumerate(files):
        r, c = divmod(i, cols) if False else (i // cols, i % cols)
        im = Image.open(path)
        if getattr(im, "is_animated", False):
            im.seek(0)
        im = im.convert("RGBA")
        if a.crop_empty: im = crop_empty(im)
        fitted = fit(im, (cw, ch), nearest=not a.bilinear)
        x = pad + c * (cw + pad)
        y = pad + r * (ch + cap_h + pad)
        ox, oy = x + (cw - fitted.width) // 2, y + (ch - fitted.height) // 2
        sheet.paste(fitted, (ox, oy), fitted)
        if cap_h:
            label = os.path.splitext(os.path.basename(path))[0]
            # clip long names
            while label and font.getlength(label) > cw and hasattr(font, "getlength"):
                label = label[:-1]
            if label:
                draw.text((x, y + ch + 1), label, fill=(240, 240, 240, 255), font=font)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    sheet.save(a.out)
    print(f"{len(files)} image(s), {cols}x{rows} cells, {W}x{H} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
