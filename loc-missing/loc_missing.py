#!/usr/bin/env python3
"""loc-missing: list localisation keys that have a source-language string but are blank or absent in one or more
other language columns. Default source is `en`. Exits 1 when anything is missing (use --no-fail for a report-only
run). `--format json|csv|text` picks the stdout/file shape. Sibling of loc-check, focused on missing rather than
placeholders or length.
"""
import argparse, os, csv, json, sys


def load_csv(path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    if not rows: sys.exit(f"{path}: empty CSV")
    return rows, list(rows[0].keys())


def collect(rows, cols, key_col, source, langs):
    missing = []
    for i, r in enumerate(rows, 2):
        key = (r.get(key_col) or "").strip()
        src = (r.get(source) or "").strip()
        if not key: continue
        if not src: continue  # source-empty keys are not "missing translations"
        for lang in langs:
            val = (r.get(lang) or "").strip()
            if not val:
                missing.append({"key": key, "lang": lang, "row": i, "source": src})
    return missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="List keys present in the source language and missing in others.")
    ap.add_argument("csv")
    ap.add_argument("--source", default="en", help="source language column (default: en)")
    ap.add_argument("--langs", help="comma list of target languages (default: every other language column)")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("-o", "--out", help="write the report (format follows --format / the path suffix)")
    ap.add_argument("--format", choices=("text", "json", "csv"), default="text")
    ap.add_argument("--no-fail", action="store_true", help="exit 0 even when keys are missing")
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

    rows, cols = load_csv(a.csv)
    if a.key not in cols: sys.exit(f"key column {a.key!r} not in CSV")
    if a.source not in cols: sys.exit(f"source column {a.source!r} not in CSV")
    skip = {a.key, "notes", "comment", "comments", "context", "max", "max_len"}
    auto = [c for c in cols if c not in skip and c != a.source]
    langs = [x.strip() for x in a.langs.split(",")] if a.langs else auto
    bad = [l for l in langs if l not in cols]
    if bad: sys.exit("unknown lang column(s): " + ", ".join(bad))
    missing = collect(rows, cols, a.key, a.source, langs)
    fmt = a.format
    if a.out and a.out.lower().endswith(".json"): fmt = "json"
    if a.out and a.out.lower().endswith(".csv"): fmt = "csv"
    if fmt == "json":
        body = json.dumps({"source": a.source, "langs": langs, "missing": len(missing), "rows": missing}, indent=1)
    elif fmt == "csv":
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["key", "lang", "row", "source"])
        w.writeheader()
        for r in missing: w.writerow(r)
        body = buf.getvalue()
    else:
        if not missing:
            body = "all keys present in " + ", ".join(langs)
        else:
            body = "\n".join(f"{r['key']}: missing {r['lang']} (row {r['row']})" for r in missing)
            body += f"\n{len(missing)} missing string(s)"
    print(body)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(body if body.endswith("\n") else body + "\n")
    return 0 if (not missing or a.no_fail) else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
