#!/usr/bin/env python3
"""font-preview: render a font at one or more sizes onto a review sheet, and list characters the font cannot draw.
Default sample: a pangram, digits, punctuation, and (with --csv) every unique character from a localisation CSV.
Each size is drawn on its own row with a label; missing glyphs are marked with a red .notdef-style box in the sheet
and listed in the report (text or JSON). Measuring uses Pillow (same metrics as loc-fit / font-check): kerning and
complex-script shaping are not applied, so Arabic or Indic lines may look wrong here even when the engine is fine.
Check the font's licence before shipping it.
"""
import argparse, os, csv, json, sys

from PIL import Image, ImageDraw, ImageFont

PANGRAM = "The quick brown fox jumps over the lazy dog."
DIGITS = "0123456789 +−-×÷= €$£¥ %.,;:?! @#&*()[]{}'\" /\\\\"


def load_font(path, size):
    if path: return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def cmap_codepoints(path):
    """Unicode code points the font actually has, via fontTools. None if fontTools or the file is unavailable
    (Pillow's default font has no cmap; missing glyphs then cannot be told from a .notdef tofu)."""
    if not path: return None
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(path); cps = set()
        for t in font["cmap"].tables: cps.update(t.cmap.keys())
        return cps
    except Exception:
        return None


def missing_chars(font, text, cmap=None):
    """Characters the font cannot draw. When a cmap is given (preferred), any non-whitespace character
    whose code point is absent is missing. Otherwise a glyph with no ink is missing; a .notdef tofu (which
    has ink) cannot be detected this way, so pass a cmap for real TTF/OTF files."""
    miss = []
    for ch in text:
        if ch.isspace(): continue
        if cmap is not None:
            if ord(ch) not in cmap: miss.append(ch)
            continue
        bb = font.getbbox(ch)
        if bb is None or bb[2] - bb[0] <= 0 or bb[3] - bb[1] <= 0: miss.append(ch)
    return list(dict.fromkeys(miss))


def unique_from_csv(path, langs=None):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    cols = langs or [c for c in (rows[0].keys() if rows else []) if c != "id"]
    return "".join(dict.fromkeys(ch for r in rows for c in cols for ch in (r.get(c) or "")))


def render_sheet(font_path, sizes, samples, bg=(30, 30, 36), fg=(240, 240, 240), pad=16, line_gap=6):
    rows, miss_all, width = [], [], pad * 2
    cmap = cmap_codepoints(font_path)
    for size in sizes:
        font = load_font(font_path, size); lines = []
        for s in samples:
            miss = missing_chars(font, s, cmap); miss_all.extend(miss)
            lines.append((s, miss))
            # width of the label + the sample
            label = f"{size}px  "
            width = max(width, pad * 2 + int(font.getlength(label + s)) + 8)
        rows.append((size, font, lines))
    # height
    h = pad
    for size, font, lines in rows:
        h += int((font.getbbox("Hg") or (0, 0, 0, size))[3] - (font.getbbox("Hg") or (0, 0, 0, 0))[1] + line_gap) * len(lines) + pad
    im = Image.new("RGB", (max(width, 200), max(h, 40)), bg); d = ImageDraw.Draw(im); y = pad
    for size, font, lines in rows:
        ascent = -(font.getbbox("Hg") or (0, -size, 0, 0))[1]
        for s, miss in lines:
            d.text((pad, y), f"{size}px  " + s, font=font, fill=fg)
            # red boxes over missing glyphs
            if miss:
                x = pad + font.getlength(f"{size}px  ")
                for ch in s:
                    cw = font.getlength(ch)
                    if ch in miss:
                        d.rectangle((x, y, x + max(cw, 4) - 1, y + size), outline=(220, 50, 50), width=1)
                    x += cw
            y += size + line_gap
        y += pad
    return im, list(dict.fromkeys(miss_all))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a font review sheet and list missing glyphs.")
    ap.add_argument("font", help="TTF/OTF (or 'default' for Pillow's bundled font)")
    ap.add_argument("-o", "--out", required=True, help="preview PNG")
    ap.add_argument("--sizes", default="16,24,32", help="comma list of px sizes")
    ap.add_argument("--text", action="append", default=[], help="extra sample line (repeatable)")
    ap.add_argument("--csv", help="localisation CSV; unique characters are included as a sample line")
    ap.add_argument("--no-pangram", action="store_true"); ap.add_argument("--json")
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
    _src_keys = ('font',)
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

    sizes = [int(s) for s in a.sizes.split(",") if s]
    samples = [] if a.no_pangram else [PANGRAM, DIGITS]
    samples += a.text
    if a.csv:
        chars = unique_from_csv(a.csv)
        samples.append(chars if len(chars) <= 200 else chars[:200] + "…")
    if not samples: sys.exit("no sample text (give --text, --csv, or leave the pangram on)")
    font_path = None if a.font in ("default", "none") else a.font
    im, miss = render_sheet(font_path, sizes, samples)
    im.save(a.out)
    print(f"{len(sizes)} size(s), {sum(len(s) for s in samples)} sample character(s), {len(miss)} missing -> {a.out}")
    if miss: print("missing: " + " ".join(repr(c) for c in miss[:80]) + (" …" if len(miss) > 80 else ""))
    if a.json: json.dump({"sizes": sizes, "missing": miss}, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if miss else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
