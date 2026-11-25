#!/usr/bin/env python3
"""loc-icu-extract: pull ICU `{var, plural, ...}` message forms and gettext-style key
suffixes (`.zero` / `.one` / `.two` / `.few` / `.many` / `.other`) out of a loc CSV into a
review table (CSV or JSON). Each row records the key, language, style, variable, categories
present, categories the language still needs, and the source text. Writes a new file; the
input is never overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-plurals"))
import safe_out, loc_plurals  # noqa: E402


def required_for(lang, no_lang_cats=False):
    if no_lang_cats:
        return ["other"]
    return list(loc_plurals.LANG_CATS.get(lang.lower(), loc_plurals.LANG_CATS.get(lang.split("-")[0].lower(), ("other",))))


def extract_rows(rows, cols, key_col, langs, no_lang_cats=False):
    out = []
    for i, r in enumerate(rows, 2):
        key = (r.get(key_col) or "").strip()
        if not key:
            continue
        for lang in langs:
            text = r.get(lang) or ""
            req = required_for(lang, no_lang_cats)
            for var, cats, body in loc_plurals.icu_categories(text):
                have = sorted(cats)
                missing = [c for c in req if c not in cats]
                out.append({
                    "key": key, "language": lang, "row": i, "style": "icu",
                    "variable": var, "categories": ",".join(have),
                    "missing": ",".join(missing), "text": text,
                })
    families, _bare = loc_plurals.suffix_families(rows, key_col)
    for stem, cats in families.items():
        have = sorted(cats)
        # one review row per language that has any member of the family
        lang_seen = set()
        for cat, (_ri, _key, row) in cats.items():
            for lang in langs:
                if lang in lang_seen:
                    continue
                # include the language if any family key has a non-empty cell
                if any((row2.get(lang) or "").strip() for _c, (_i, _k, row2) in cats.items()):
                    lang_seen.add(lang)
                    req = required_for(lang, no_lang_cats)
                    present = sorted(c for c, (_i, _k, row2) in cats.items() if (row2.get(lang) or "").strip())
                    missing = [c for c in req if c not in present]
                    # representative text: prefer .other then first
                    text = ""
                    for pref in ("other", "one", "few", "many", "two", "zero"):
                        if pref in cats and (cats[pref][2].get(lang) or "").strip():
                            text = cats[pref][2].get(lang) or ""
                            break
                    if not text:
                        text = next((row2.get(lang) or "" for _c, (_i, _k, row2) in cats.items() if (row2.get(lang) or "").strip()), "")
                    out.append({
                        "key": stem, "language": lang, "row": cats[have[0]][0] if have else "",
                        "style": "suffix", "variable": "", "categories": ",".join(present),
                        "missing": ",".join(missing), "text": text,
                    })
    return out


FIELDS = ["key", "language", "row", "style", "variable", "categories", "missing", "text"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract ICU and suffix plural forms from a loc CSV into a review table.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", required=True, help="review table (.csv or .json)")
    ap.add_argument("--source", default="en")
    ap.add_argument("--langs", help="comma list of language columns (default: every non-key column)")
    ap.add_argument("--key", default="id")
    ap.add_argument("--no-lang-cats", action="store_true")
    ap.add_argument("--json", help="write the same table as JSON next to / instead of inferring from -o")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    rows, cols = loc_plurals.load_csv(a.csv)
    if a.key not in cols:
        sys.exit(f"key column {a.key!r} not in CSV")
    langs = loc_plurals.lang_columns(cols, a.key, a.source, a.langs)
    table = extract_rows(rows, cols, a.key, langs, a.no_lang_cats)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    ext = os.path.splitext(a.out)[1].lower()
    if ext == ".json":
        json.dump(table, open(a.out, "w"), indent=1, ensure_ascii=False)
    else:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for r in table:
                w.writerow(r)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"count": len(table), "rows": table, "out": a.out}, open(a.json, "w"), indent=1, ensure_ascii=False)
    print(f"{len(table)} plural form(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
