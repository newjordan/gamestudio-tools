#!/usr/bin/env python3
"""loc-check: validate a multi-language strings CSV (columns: id, <source lang>, <other langs>...).

Errors: duplicate ids, missing/empty translation, placeholder mismatch ({name}, %s, %d, %1$s, $var$),
tag mismatch (<b>, [color]), escape mismatch (\\n). Warnings: translation identical to source (maybe
untranslated), length over --max-ratio of the source and at least 6 characters longer (UI overflow risk; languages with CJK get a separate
--max-ratio-cjk because they are naturally shorter in characters), leading/trailing whitespace changes.
Exit 1 on errors (or warnings with --strict).
"""
import os
import argparse, csv, json, re, sys
from collections import Counter

PH = re.compile(r"\{[^{}]*\}|%\d*\$?[sdif]|%%|\$[A-Za-z_]+\$")
TAG = re.compile(r"<[^>]+>|\[/?[a-zA-Z][^\]]*\]")
ESC = re.compile(r"\\[nrt]")
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def multiset(rx, s):
    return Counter(rx.findall(s))


def check(rows, src, langs, max_ratio=1.6, max_ratio_cjk=1.0):
    out = []
    add = lambda lvl, i, lang, msg: out.append({"level": lvl, "id": i, "lang": lang, "msg": msg})
    ids = Counter(r["id"] for r in rows)
    for i, n in ids.items():
        if n > 1: add("error", i, "", f"duplicate id ({n}x)")
    for r in rows:
        s = r.get(src, "")
        for lang in langs:
            t = r.get(lang, "")
            if not t.strip():
                add("error", r["id"], lang, "missing translation"); continue
            for name, rx in (("placeholder", PH), ("tag", TAG), ("escape", ESC)):
                a, b = multiset(rx, s), multiset(rx, t)
                if a != b:
                    miss, extra = list((a - b).elements()), list((b - a).elements())
                    add("error", r["id"], lang, f"{name} mismatch" + (f", missing {miss}" if miss else "") + (f", unexpected {extra}" if extra else ""))
            if t == s and len(s) > 3 and re.search(r"[A-Za-z]{3,}", s): add("warn", r["id"], lang, "identical to source (untranslated?)")
            limit = max_ratio_cjk if CJK.search(t) else max_ratio
            if len(t) - len(s) >= 6 and len(t) > len(s) * limit: add("warn", r["id"], lang, f"length {len(t)} is {len(t) / len(s):.1f}x source ({len(s)}), limit {limit}x")
            if s != s.strip() and t == t.strip() or t != t.strip() and s == s.strip(): add("warn", r["id"], lang, "leading/trailing whitespace differs from source")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate a localisation CSV.")
    ap.add_argument("csv"); ap.add_argument("--source", default="en"); ap.add_argument("--langs", help="comma list (default: every other column)")
    ap.add_argument("--max-ratio", type=float, default=1.6); ap.add_argument("--max-ratio-cjk", type=float, default=1.0)
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--json")
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
    if a.source not in cols: sys.exit(f"source column {a.source!r} not in {cols}")
    langs = a.langs.split(",") if a.langs else [c for c in cols if c not in ("id", a.source)]
    res = check(rows, a.source, langs, a.max_ratio, a.max_ratio_cjk)
    for r in res: print(f"{r['level'].upper():5} {r['id']} [{r['lang'] or '-'}]: {r['msg']}")
    e = sum(r["level"] == "error" for r in res); w = len(res) - e
    print(f"{len(rows)} string(s), {len(langs)} language(s): {e} error(s), {w} warning(s)")
    if a.json: json.dump(res, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if e or (a.strict and w) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
