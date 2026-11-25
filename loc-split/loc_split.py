#!/usr/bin/env python3
"""loc-split: split a multi-language localisation CSV into per-language files
(`{stem}_{lang}.csv` with the key column plus that language). The inverse of a
later loc-join. The input is never overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-merge"))
import safe_out, loc_merge  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a multi-language loc CSV into per-language files.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--outdir", required=True, help="directory for per-language CSVs")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    # refuse writing into the input path if someone passes the csv as outdir somehow
    safe_out.check(a.csv, a.outdir, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    by, cols, dups = loc_merge.load_csv(a.csv, a.key)
    langs = [c for c in cols if c != a.key and c != "_row"]
    if not langs:
        sys.exit("no language columns to split")
    os.makedirs(a.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.csv))[0]
    files = []
    keys = list(by)
    for lang in langs:
        dest = os.path.join(a.outdir, f"{stem}_{lang}.csv")
        safe_out.check(a.csv, dest, a.in_place)
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=[a.key, lang], extrasaction="ignore")
            w.writeheader()
            for k in keys:
                rec = by[k]
                w.writerow({a.key: k, lang: rec.get(lang) or ""})
        files.append({"lang": lang, "out": dest, "rows": len(keys)})
    rec = {"outdir": a.outdir, "languages": langs, "keys": len(keys), "files": files,
           "duplicates_in": dups}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(langs)} language file(s), {len(keys)} key(s) -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
