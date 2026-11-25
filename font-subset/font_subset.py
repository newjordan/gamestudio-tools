#!/usr/bin/env python3
"""font-subset: shrink a TTF/OTF to just the characters your game needs (every character found in the given text/CSV/yarn/ink files,
plus --chars, plus --ascii for U+0020..007E). Uses fontTools (pip install fonttools); layout features (kerning, ligatures)
are kept, hinting can be dropped with --drop-hinting, and --flavor woff writes WOFF (woff2 needs the brotli package). Prints the
size before and after and any requested characters the font does not have. Check that the font's licence allows subsetting and
embedding: SIL OFL fonts do, some commercial fonts do not. Pairs with font-check (what is missing) and bmfont-gen (bitmap fonts).
"""
import argparse, os, sys, logging

try:
    from fontTools import subset
    from fontTools.ttLib import TTFont
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)                  # "table X NOT subset" notices are noise here
except Exception:
    subset = TTFont = None


def used_chars(paths, extra="", ascii_=False):
    s = set(extra) | {" "}
    if ascii_: s |= {chr(c) for c in range(0x20, 0x7F)}
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f: s |= {c for c in f.read() if c.isprintable()}
    return s


def do_subset(font_path, chars, out, drop_hinting=False, flavor=None):
    if subset is None: raise SystemExit("font-subset needs fontTools: pip install fonttools")
    f = TTFont(font_path, fontNumber=0); cmap = f.getBestCmap() or {}
    missing = sorted((c for c in chars if ord(c) not in cmap), key=ord)
    opts = subset.Options(); opts.layout_features = ["*"]; opts.name_IDs = ["*"]; opts.notdef_outline = True; opts.hinting = not drop_hinting
    if flavor:
        if flavor == "woff2":
            try: import brotli  # noqa: F401
            except ImportError: raise SystemExit("woff2 needs the brotli package; use --flavor woff or install brotli")
        opts.flavor = flavor
    sub = subset.Subsetter(opts); sub.populate(unicodes=[ord(c) for c in chars if c not in missing]); sub.subset(f)
    f.flavor = flavor or f.flavor; os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); f.save(out)
    return {"before": os.path.getsize(font_path), "after": os.path.getsize(out), "kept": len(chars) - len(missing), "missing": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Subset a font to the characters you use.")
    ap.add_argument("font"); ap.add_argument("texts", nargs="*"); ap.add_argument("-o", "--out"); ap.add_argument("--chars", default=""); ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--drop-hinting", action="store_true"); ap.add_argument("--flavor", choices=["woff", "woff2"])
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); chars = used_chars(a.texts, a.chars, a.ascii)
    if len(chars) <= 1: ap.error("no characters: give text files, --chars or --ascii")
    stem, ext = os.path.splitext(a.font); out = a.out or f"{stem}-subset{('.' + a.flavor) if a.flavor else ext}"
    if os.path.abspath(out) == os.path.abspath(a.font) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    r = do_subset(a.font, chars, out, a.drop_hinting, a.flavor)
    print(f"{a.font}: {r['before']} -> {r['after']} bytes ({100 * r['after'] / r['before']:.1f}%), {r['kept']} character(s) kept -> {out}")
    if r["missing"]: print("not in the font: " + " ".join(f"{c}(U+{ord(c):04X})" for c in r["missing"][:30]))
    print("note: check the font licence allows subsetting and embedding."); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
