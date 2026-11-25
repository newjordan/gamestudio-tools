#!/usr/bin/env python3
"""loc-diff: compare two localisation CSVs by key. Reports keys only in A or only
in B, and cells that changed in shared language columns (matched by name). Exit 1
when anything differs unless `--no-fail`. Optional `--json` report and `--out` CSV
of added, removed and changed rows. The inputs are never overwritten unless
`--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-merge"))
import safe_out, loc_merge  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff two localisation CSVs by key and language column.")
    ap.add_argument("csv_a")
    ap.add_argument("csv_b")
    ap.add_argument("-o", "--out", help="CSV of added, removed and changed rows")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--json", help="report path")
    ap.add_argument("--no-fail", action="store_true", help="exit 0 even when the tables differ")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    sources = [a.csv_a, a.csv_b]
    if a.out:
        safe_out.check_any(sources, a.out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    a_by, a_cols, dups_a = loc_merge.load_csv(a.csv_a, a.key)
    b_by, b_cols, dups_b = loc_merge.load_csv(a.csv_b, a.key)
    langs = []
    for c in a_cols + b_cols:
        if c != a.key and c not in langs:
            langs.append(c)
    only_a = [k for k in a_by if k not in b_by]
    only_b = [k for k in b_by if k not in a_by]
    changes = []
    for k in a_by:
        if k not in b_by:
            continue
        ra, rb = a_by[k], b_by[k]
        cells = []
        for c in langs:
            va, vb = (ra.get(c) or ""), (rb.get(c) or "")
            # a column missing from one file is an empty cell on that side
            if va != vb:
                cells.append({"column": c, "a": va, "b": vb})
        if cells:
            changes.append({"key": k, "cells": cells})
    rec = {"only_in_a": only_a, "only_in_b": only_b, "changed": changes,
           "duplicates": dups_a + dups_b, "languages": langs}
    differ = bool(only_a or only_b or changes or dups_a or dups_b)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        fields = [a.key, "status"] + langs
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for k in only_a:
                row = {a.key: k, "status": "removed"}
                for c in langs:
                    row[c] = a_by[k].get(c) or ""
                w.writerow(row)
            for k in only_b:
                row = {a.key: k, "status": "added"}
                for c in langs:
                    row[c] = b_by[k].get(c) or ""
                w.writerow(row)
            for ch in changes:
                k = ch["key"]
                row = {a.key: k, "status": "changed"}
                for c in langs:
                    va, vb = (a_by[k].get(c) or ""), (b_by[k].get(c) or "")
                    row[c] = vb if va != vb else va
                w.writerow(row)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(only_a)} only in A, {len(only_b)} only in B, {len(changes)} changed key(s)"
          + (f" -> {a.out}" if a.out else ""))
    if differ and not a.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
