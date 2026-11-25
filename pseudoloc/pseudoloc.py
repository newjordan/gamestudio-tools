#!/usr/bin/env python3
"""pseudoloc: pseudo-localise a strings CSV to find UI overflow, hard-coded text and encoding bugs
before real translations exist. Accents Latin letters, pads text by ~30-40% with a filler tail, and
wraps in [ ] brackets so truncated text is obvious. Placeholders ({name}, {0}, %s, %d, %1$s, $var$),
<tags>, [markup] and escapes (\\n) are left untouched.
"""
import os
import argparse, csv, re
import sys

MAP = str.maketrans("AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz",
                    "ÀåƁƀÇçĐďÉéƑƒĜģĤħÎīĴĵĶķĹłṀṁÑñÖöÞþǬǫŔřŠšŤţÛüṾṿŴŵẊẋÝýŽž")
PROTECT = re.compile(r"(\{[^{}]*\}|%\d*\$?[sdif]|%%|<[^>]+>|\[/?[a-zA-Z][^\]]*\]|\\[nrt]|\$[A-Za-z_]+\$)")
FILL = " ·ƒıḷḷ ēř"


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def pseudo(text, expand=0.35, brackets=True):
    parts = PROTECT.split(text)
    out = "".join(p if PROTECT.fullmatch(p) else p.translate(MAP) for p in parts)
    n_extra = max(2, round(len(text) * expand))
    tail = (FILL * (n_extra // len(FILL) + 1))[:n_extra]
    out = out + tail
    return f"[{out}]" if brackets else out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pseudo-localise a strings CSV.")
    ap.add_argument("csv"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--column", default="text", help="column to transform (default: text)")
    ap.add_argument("--new-column", help="write to this new column instead of replacing")
    ap.add_argument("--expand", type=float, default=0.35)
    ap.add_argument("--no-brackets", action="store_true")
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
    if a.column not in cols: raise GstInputError("no column %r; have %s" % (a.column, cols))
    dst = a.new_column or a.column
    if dst not in cols: cols.append(dst)
    for r in rows: r[dst] = pseudo(r[a.column], a.expand, not a.no_brackets)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"pseudo-localised {len(rows)} string(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
