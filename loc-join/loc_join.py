#!/usr/bin/env python3
"""loc-join: join per-language localisation CSVs into one multi-language table
(the inverse of loc-split). Each input is `key + one or more language columns`
(typically `{stem}_{lang}.csv`). Keys are the union of every file (missing
cells stay empty). First-wins on duplicate keys inside a file. The input is
never overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-merge"))
import safe_out, loc_merge  # noqa: E402


def collect(inputs):
    paths = []
    for p in inputs:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(".csv"):
                    paths.append(os.path.join(p, name))
        else:
            paths.append(p)
    if not paths:
        raise SystemExit("no CSV files found")
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser(description="Join per-language loc CSVs into one multi-language table.")
    ap.add_argument("inputs", nargs="+", help="per-language CSVs or a folder of them")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--langs", help="comma-separated language column order (default: input file order)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    paths = collect(a.inputs)
    safe_out.check_any(paths, a.out, a.in_place)
    if a.json:
        safe_out.check_any(paths, a.json, a.in_place)
    tables = []
    all_langs = []
    dups = []
    for p in paths:
        by, cols, dup = loc_merge.load_csv(p, a.key)
        langs = [c for c in cols if c != a.key and c != "_row"]
        if not langs:
            raise SystemExit(f"{p}: no language columns")
        for lang in langs:
            if lang not in all_langs:
                all_langs.append(lang)
        tables.append((p, by, langs))
        dups.extend(dup)
    if a.langs:
        wanted = [x.strip() for x in a.langs.split(",") if x.strip()]
        missing = [x for x in wanted if x not in all_langs]
        if missing:
            raise SystemExit(f"--langs names not in the inputs: {missing}")
        all_langs = wanted
    keys = []
    seen = set()
    for _p, by, _langs in tables:
        for k in by:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    fieldnames = [a.key] + all_langs
    rows = []
    for k in keys:
        rec = {a.key: k}
        for lang in all_langs:
            rec[lang] = ""
        for _p, by, langs in tables:
            if k in by:
                for lang in langs:
                    if lang in rec and rec[lang] == "":
                        rec[lang] = by[k].get(lang) or ""
        rows.append(rec)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    rec = {"out": a.out, "files": paths, "languages": all_langs, "keys": len(keys),
           "duplicates_in": dups}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(all_langs)} language(s), {len(keys)} key(s) from {len(paths)} file(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
