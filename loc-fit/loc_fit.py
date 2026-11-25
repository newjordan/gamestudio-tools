#!/usr/bin/env python3
"""loc-fit: will the translated string fit its UI box? Measures every string in a localisation CSV (id + one column per language, as
loc-check reads) with a real font at a given size and compares the pixel width with a per-string limit. Strings that do not fit on
one line are word-wrapped to the limit (character wrapped for CJK or text with no spaces) and judged against --max-lines (default 1).
Limits: --limit-default PX, a limits CSV (id,max_px[,max_lines]; ids may be fnmatch patterns such as menu.*), or both (file wins).
Placeholders {name}, %d, %s and markup tags are replaced: {...}/%x by --placeholder text (default "0000"), <tags> removed.
Reports width, ratio to the limit, lines needed and a wrapped suggestion; text, CSV or JSON; exit 1 on overflow.
Measuring uses Pillow's font metrics (no kerning/shaping beyond Pillow's basic layout; complex scripts need an engine check).
"""
import os
import argparse, csv, fnmatch, os, sys, json, re, sys

from PIL import ImageFont

PH = re.compile(r"\{[^}]*\}|%[-+ 0#]*\d*(?:\.\d+)?[sdif]|%%")
TAG = re.compile(r"</?[A-Za-z][^>]*>|\[/?[a-z][^\]]*\]")


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def prepare(text, placeholder="0000"):
    t = TAG.sub("", text); return PH.sub(lambda m: "%" if m.group(0) == "%%" else placeholder, t)


def measure(font, s): return font.getlength(s)


def wrap(font, text, limit):
    """Greedy wrap to `limit` px. Words are kept whole unless a single word is wider than the limit (then split by characters).
    Text without spaces (CJK) wraps by character. Returns the list of lines."""
    lines = []
    for para in text.split("\n"):
        words = para.split(" ") if " " in para else list(para)
        sep = " " if " " in para else ""; cur = ""
        for w in words:
            trial = w if not cur else cur + sep + w
            if measure(font, trial) <= limit or not cur and measure(font, w) <= limit: cur = trial; continue
            if cur: lines.append(cur); cur = ""
            while measure(font, w) > limit and len(w) > 1:                          # a single word that is too wide: break by characters
                k = max(1, next((i for i in range(len(w), 0, -1) if measure(font, w[:i]) <= limit), 1)); lines.append(w[:k]); w = w[k:]
            cur = w
        lines.append(cur)
    return lines


def load_limits(path):
    out = []
    if not path: return out
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        out.append((r["id"], float(r["max_px"]), int(r.get("max_lines") or 0) or None))
    return out


def limit_for(sid, limits, default, default_lines):
    for pat, px, ml in limits:
        if fnmatch.fnmatchcase(sid, pat): return px, ml or default_lines
    return default, default_lines


def check(rows, langs, font, limits, default, default_lines=1, placeholder="0000", id_col="id"):
    res = []
    for r in rows:
        sid = r[id_col]; px, ml = limit_for(sid, limits, default, default_lines)
        if px is None: continue
        for lang in langs:
            raw = r.get(lang) or ""
            if not raw.strip(): continue
            t = prepare(raw, placeholder); w = measure(font, t) if "\n" not in t else max(measure(font, p) for p in t.split("\n")); lines = wrap(font, t, px) if (w > px or "\n" in t) else [t]
            res.append({"id": sid, "lang": lang, "width_px": round(w, 1), "limit_px": px, "ratio": round(w / px, 2) if px else None, "lines": len(lines), "max_lines": ml,
                        "fits": len(lines) <= ml, "wrapped": "\n".join(lines)})
    return res


def load_font(path, size):
    if path: return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check localised strings fit their UI boxes.")
    ap.add_argument("csv"); ap.add_argument("--font", help="TTF/OTF file (default: Pillow's built-in font)"); ap.add_argument("--size", type=int, default=16)
    ap.add_argument("--limits", help="CSV: id,max_px[,max_lines] (id may be a glob)"); ap.add_argument("--limit-default", type=float); ap.add_argument("--max-lines", type=int, default=1)
    ap.add_argument("--langs", help="comma list (default: every column except id)"); ap.add_argument("--placeholder", default="0000"); ap.add_argument("--only-failing", action="store_true")
    ap.add_argument("--out-csv"); ap.add_argument("--json")
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
    _src_keys = ('csv',)
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

    rows, cols = gst_read.load_loc_csv(a.csv)
    if "id" not in cols: raise GstInputError("CSV needs an 'id' column")
    langs = a.langs.split(",") if a.langs else [c for c in cols if c != "id"]
    limits = load_limits(a.limits)
    if not limits and a.limit_default is None: sys.exit("give --limits FILE and/or --limit-default PX")
    res = check(rows, langs, load_font(a.font, a.size), limits, a.limit_default, a.max_lines, a.placeholder)
    bad = [r for r in res if not r["fits"]]
    for r in (bad if a.only_failing else res):
        print(f"{'ok  ' if r['fits'] else 'FAIL'} {r['id']} [{r['lang']}] {r['width_px']:.0f}px / {r['limit_px']:.0f}px ({r['ratio']:.2f}x), {r['lines']} line(s) of {r['max_lines']}" + ("" if r["fits"] else "  -> " + r["wrapped"].replace("\n", " / ")))
    print(f"{len(res)} string(s) measured, {len(bad)} do not fit")
    if a.out_csv:
        with open(a.out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(res[0]) if res else ["id"]); w.writeheader(); w.writerows(res)
    if a.json: json.dump(res, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
