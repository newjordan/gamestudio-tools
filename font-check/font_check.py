#!/usr/bin/env python3
"""font-check: find the characters your game text needs that a font does not contain (they would render as
empty boxes). Inputs: CSV/TXT/JSON/yarn/ink files (every character is collected, placeholders and markup
included, so run it on real strings), and one or more fonts: .ttf/.otf/.ttc (cmap via fontTools when installed,
otherwise a render comparison against the font's missing-glyph box) or BMFont .fnt (char ids).
Prints per font which characters are missing, with code points, and exits 1 if any are. Whitespace and control
characters are ignored.
"""
import argparse, os, collections, json, re, sys

try:
    from fontTools.ttLib import TTFont
except Exception:  # fontTools is optional
    TTFont = None


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def text_chars(paths):
    cnt = collections.Counter()
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f: cnt.update(c for c in f.read() if c.isprintable() and not c.isspace())
    return cnt


def font_has(path, chars):
    """returns the set of characters from `chars` that the font can draw."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fnt":
        ids = gst_read.load_bmfont(path)
        return {c for c in chars if ord(c) in ids}
    if TTFont is not None:
        cmap = {}
        f = TTFont(path, fontNumber=0, lazy=True)
        for t in f["cmap"].tables:
            if t.isUnicode(): cmap.update(t.cmap)
        return {c for c in chars if ord(c) in cmap}
    from PIL import ImageFont
    font = ImageFont.truetype(path, 24); notdef = bytes(font.getmask("\uffff")); sz = font.getmask("\uffff").size
    return {c for c in chars if not (font.getmask(c).size == sz and bytes(font.getmask(c)) == notdef)}


def check(chars, fonts):
    return {fp: sorted(set(chars) - font_has(fp, set(chars)), key=ord) for fp in fonts}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report characters missing from fonts.")
    ap.add_argument("texts", nargs="+"); ap.add_argument("--font", action="append", required=True)
    ap.add_argument("--json"); ap.add_argument("--ignore", default="", help="characters to ignore")
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
    _src_keys = ('texts',)
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

    cnt = text_chars(a.texts)
    for c in a.ignore: cnt.pop(c, None)
    res = check(cnt, a.font); bad = False
    print(f"{len(cnt)} distinct character(s) in {len(a.texts)} file(s)")
    for fp, miss in res.items():
        if miss:
            bad = True; print(f"{fp}: MISSING {len(miss)}: " + " ".join(f"{c}(U+{ord(c):04X} x{cnt[c]})" for c in miss[:40]) + (" ..." if len(miss) > 40 else ""))
        else: print(f"{fp}: OK")
    if a.json: json.dump({fp: [{"char": c, "codepoint": f"U+{ord(c):04X}", "count": cnt[c]} for c in m] for fp, m in res.items()}, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
