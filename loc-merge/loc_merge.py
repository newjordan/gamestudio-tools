#!/usr/bin/env python3
"""loc-merge: combine two localisation CSVs by key. Language columns are unioned (A's
order first, then any new columns from B). Keys only in one file are kept and reported
as missing. When the same key has different values in a shared language, the cell is a
collision: `--prefer a|b` picks a side (default a) and the run exits 1 unless `--no-fail`.
`--prefer fail` refuses to write when any collision is present. The inputs are never
overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def load_csv(path, key_col):
    rows, cols = gst_read.load_loc_csv(path)
    if not rows:
        raise GstInputError("%s: empty CSV" % path)
    if key_col not in cols:
        raise GstInputError("%s: no key column %r (have %s)" % (path, key_col, cols))
    by = {}
    dups = []
    for i, r in enumerate(rows, start=2):
        k = (r.get(key_col) or "").strip()
        if not k:
            continue
        if k in by:
            dups.append({"file": path, "key": k, "row": i, "first_row": by[k]["_row"]})
        else:
            rec = dict(r)
            rec["_row"] = i
            by[k] = rec
    return by, cols, dups


def merge(a_by, a_cols, b_by, b_cols, key_col, prefer):
    langs_a = [c for c in a_cols if c != key_col]
    langs_b = [c for c in b_cols if c != key_col]
    cols = [key_col] + langs_a + [c for c in langs_b if c not in langs_a and c != key_col]
    keys = list(dict.fromkeys([*a_by, *b_by]))
    missing_a, missing_b, collisions, rows = [], [], [], []
    for k in keys:
        in_a, in_b = k in a_by, k in b_by
        if in_a and not in_b:
            missing_b.append(k)
        if in_b and not in_a:
            missing_a.append(k)
        ra, rb = a_by.get(k, {}), b_by.get(k, {})
        out = {key_col: k}
        for c in cols:
            if c == key_col:
                continue
            va = (ra.get(c) or "") if in_a else ""
            vb = (rb.get(c) or "") if in_b else ""
            if in_a and in_b and c in ra and c in rb and va != vb:
                collisions.append({"key": k, "column": c, "a": va, "b": vb})
                if prefer == "b":
                    out[c] = vb
                elif prefer == "a":
                    out[c] = va
                else:
                    out[c] = va  # unused if we refuse to write
            elif in_a and (c in ra or not in_b):
                out[c] = va
            else:
                out[c] = vb
        rows.append(out)
    return cols, rows, missing_a, missing_b, collisions


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge two localisation CSVs by key, flagging collisions and missing rows.")
    ap.add_argument("csv_a")
    ap.add_argument("csv_b")
    ap.add_argument("-o", "--out", required=True, help="merged CSV")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--prefer", choices=("a", "b", "fail"), default="a",
                    help="on a value collision, keep A's or B's cell, or refuse to write (default: a)")
    ap.add_argument("--json", help="report path")
    ap.add_argument("--no-fail", action="store_true", help="exit 0 even when collisions or missing keys are present")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    sources = [a.csv_a, a.csv_b]
    safe_out.check_any(sources, a.out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    a_by, a_cols, dups_a = load_csv(a.csv_a, a.key)
    b_by, b_cols, dups_b = load_csv(a.csv_b, a.key)
    cols, rows, miss_a, miss_b, collisions = merge(a_by, a_cols, b_by, b_cols, a.key, a.prefer)
    rec = {"keys": len(rows), "only_in_a": miss_b, "only_in_b": miss_a,
           "collisions": collisions, "duplicates": dups_a + dups_b,
           "columns": cols, "out": a.out}
    can_write = not (a.prefer == "fail" and collisions)
    if can_write:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(rows)} key(s), {len(miss_b)} only in A, {len(miss_a)} only in B, "
          f"{len(collisions)} collision(s)" + (f" -> {a.out}" if can_write else " (not written)"))
    if not can_write:
        sys.exit("collisions present; not writing (pass --prefer a|b or fix the rows)")
    if (collisions or miss_a or miss_b or dups_a or dups_b) and not a.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
