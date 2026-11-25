#!/usr/bin/env python3
"""loc-stats: summarise a localisation CSV — key counts, per-language fill rates,
character and word counts, longest strings, and duplicate keys. The CSV is not
rewritten. --json / --csv output paths may not overwrite the input unless
`--in-place` is given.
"""
from __future__ import annotations

import argparse, os, csv, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

WORD_RE = re.compile(r"\S+", re.UNICODE)


def words_of(s):
    return len(WORD_RE.findall(s or ""))


def analyse(path, key_col):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
    if not rows:
        raise SystemExit(f"{path}: empty CSV")
    cols = list(rows[0].keys())
    if key_col not in cols:
        raise SystemExit(f"{path}: no key column {key_col!r} (have {cols})")
    langs = [c for c in cols if c != key_col]
    by = {}
    dups = []
    blanks = 0
    for i, r in enumerate(rows, start=2):
        k = (r.get(key_col) or "").strip()
        if not k:
            blanks += 1
            continue
        if k in by:
            dups.append({"key": k, "row": i, "first_row": by[k]["_row"]})
        else:
            rec = dict(r)
            rec["_row"] = i
            by[k] = rec
    keys = list(by)
    languages = []
    for lang in langs:
        filled = empty = chars = words = 0
        longest_key, longest_len, longest = "", 0, ""
        for k, rec in by.items():
            val = rec.get(lang) or ""
            if val.strip():
                filled += 1
                n = len(val)
                chars += n
                words += words_of(val)
                if n > longest_len:
                    longest_len, longest_key, longest = n, k, val
            else:
                empty += 1
        nkeys = len(keys)
        languages.append({
            "language": lang,
            "filled": filled,
            "empty": empty,
            "fill_rate": (filled / nkeys) if nkeys else 0.0,
            "chars": chars,
            "words": words,
            "longest_key": longest_key,
            "longest_len": longest_len,
            "longest": longest[:200],
        })
    return {
        "keys": len(keys),
        "rows": len(rows),
        "blank_keys": blanks,
        "duplicate_keys": len(dups),
        "duplicates": dups,
        "languages": languages,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Summarise a localisation CSV (fill rates, lengths, duplicate keys).")
    ap.add_argument("csv")
    ap.add_argument("--key", default="id")
    ap.add_argument("--json")
    ap.add_argument("--csv", dest="csv_out", help="per-language summary CSV")
    ap.add_argument("--fail-if-empty-gt", type=float,
                    help="exit 1 if any language's empty rate (0-1) is greater than this")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    if a.csv_out:
        safe_out.check(a.csv, a.csv_out, a.in_place)
    rec = analyse(a.csv, a.key)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2, ensure_ascii=False)
    if a.csv_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.csv_out)) or ".", exist_ok=True)
        fields = ["language", "filled", "empty", "fill_rate", "chars", "words", "longest_key", "longest_len"]
        with open(a.csv_out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for row in rec["languages"]:
                out = dict(row)
                out["fill_rate"] = f"{out['fill_rate']:.4f}"
                w.writerow(out)
    bits = ", ".join("%s %d/%d" % (L["language"], L["filled"], rec["keys"]) for L in rec["languages"])
    print("%d key(s), %d language(s), %d duplicate(s) -> %s" % (
        rec["keys"], len(rec["languages"]), rec["duplicate_keys"], bits))
    if a.fail_if_empty_gt is not None:
        bad = [L for L in rec["languages"] if (1.0 - L["fill_rate"]) > a.fail_if_empty_gt + 1e-12]
        if bad:
            names = ", ".join(L["language"] for L in bad)
            print("empty rate above %s: %s" % (a.fail_if_empty_gt, names), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
