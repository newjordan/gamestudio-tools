#!/usr/bin/env python3
"""loc-sort: sort a loc CSV by the key column (stable), keep the header, and report
duplicate keys. Writes a new CSV; the input is never overwritten unless `--in-place`.
Exit 1 when duplicates are found, unless `--no-fail`.
"""
import argparse, os, csv, json, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sort a loc CSV by key and report duplicate keys.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--desc", action="store_true", help="sort descending")
    ap.add_argument("--no-fail", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    with open(a.csv, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not fields:
        sys.exit("CSV has no header")
    if a.key not in fields:
        sys.exit(f"key column {a.key!r} not in CSV")
    rows_sorted = sorted(rows, key=lambda r: (r.get(a.key) or ""), reverse=a.desc)
    keys = [(r.get(a.key) or "") for r in rows_sorted]
    counts = Counter(k for k in keys if k)
    dupes = sorted(k for k, n in counts.items() if n > 1)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_sorted)
    rec = {"rows": len(rows_sorted), "duplicates": dupes,
           "duplicate_counts": {k: counts[k] for k in dupes}, "out": a.out}
    print(f"{len(rows_sorted)} row(s)" + (f", {len(dupes)} duplicate key(s)" if dupes else "") + f" -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0 if (a.no_fail or not dupes) else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
