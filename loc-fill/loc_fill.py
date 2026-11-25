#!/usr/bin/env python3
"""loc-fill: fill empty cells in a localisation CSV from a source-language
column (default `en`). Non-empty target cells are left alone unless
`--overwrite`. Optional `--prefix` is prepended to the filled value (for
translator marks). First-wins on duplicate keys, like loc-merge. The input is
never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

SKIP = {"notes", "comment", "comments", "context", "max", "max_len"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fill empty localisation CSV cells from a source language.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", required=True, help="filled CSV")
    ap.add_argument("--source", default="en", help="source language column (default: en)")
    ap.add_argument("--langs", help="comma list of target languages (default: every other language column)")
    ap.add_argument("--key", default="id")
    ap.add_argument("--prefix", default="", help="prepended to each filled value")
    ap.add_argument("--overwrite", action="store_true", help="replace non-empty target cells too")
    ap.add_argument("--json")
    ap.add_argument("--fail-if-empty", action="store_true",
                    help="exit 1 if any target cell is still empty after the fill")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)

    rows = list(csv.DictReader(open(a.csv, newline="", encoding="utf-8-sig")))
    if not rows:
        raise SystemExit(f"{a.csv}: empty CSV")
    cols = list(rows[0].keys())
    if a.key not in cols:
        raise SystemExit(f"key column {a.key!r} not in CSV")
    if a.source not in cols:
        raise SystemExit(f"source column {a.source!r} not in CSV")
    auto = [c for c in cols if c != a.key and c not in SKIP and c != a.source]
    langs = [x.strip() for x in a.langs.split(",")] if a.langs else auto
    bad = [l for l in langs if l not in cols]
    if bad:
        raise SystemExit("unknown lang column(s): " + ", ".join(bad))

    seen = set()
    filled = 0
    skipped_dups = 0
    still_empty = 0
    out_rows = []
    for i, r in enumerate(rows, start=2):
        rec = {c: r.get(c, "") for c in cols}
        k = (rec.get(a.key) or "").strip()
        if k and k in seen:
            skipped_dups += 1
        elif k:
            seen.add(k)
        src = rec.get(a.source) or ""
        for lang in langs:
            val = rec.get(lang) or ""
            if (not val.strip()) or a.overwrite:
                if src.strip():
                    rec[lang] = (a.prefix or "") + src
                    filled += 1
                elif not val.strip():
                    still_empty += 1
            if not (rec.get(lang) or "").strip():
                still_empty += 1 if lang and (rec.get(lang) or "") == val and not src.strip() else 0
        # recount still_empty cleanly below
        out_rows.append(rec)

    still_empty = 0
    for rec in out_rows:
        if not (rec.get(a.source) or "").strip() and not (rec.get(a.key) or "").strip():
            pass
        for lang in langs:
            if not (rec.get(lang) or "").strip():
                still_empty += 1

    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    rec = {"out": a.out, "keys": len(seen), "langs": langs, "source": a.source,
           "filled": filled, "duplicate_keys": skipped_dups, "still_empty": still_empty,
           "overwrite": bool(a.overwrite)}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("filled %d cell(s), %d still empty -> %s" % (filled, still_empty, a.out))
    if a.fail_if_empty and still_empty:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
