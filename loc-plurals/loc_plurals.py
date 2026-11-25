#!/usr/bin/env python3
"""loc-plurals: check ICU `{var, plural, ...}` messages and gettext-style key suffixes
(`.zero` / `.one` / `.two` / `.few` / `.many` / `.other`) across language columns of a loc CSV.
Exits 1 when a plural is missing `other`, a suffix family is incomplete, or a translation is
missing a plural that the source has (use --no-fail for a report-only run).
"""
import argparse, os, sys, csv, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

CATS = ("zero", "one", "two", "few", "many", "other")
# CLDR cardinal categories commonly required (other is always required separately).
LANG_CATS = {
    "en": ("one", "other"), "de": ("one", "other"), "nl": ("one", "other"), "sv": ("one", "other"),
    "es": ("one", "other"), "it": ("one", "other"), "pt": ("one", "other"),
    "fr": ("one", "many", "other"), "pt-br": ("one", "many", "other"),
    "ru": ("one", "few", "many", "other"), "uk": ("one", "few", "many", "other"),
    "pl": ("one", "few", "many", "other"), "cs": ("one", "few", "other"),
    "ar": ("zero", "one", "two", "few", "many", "other"),
    "ja": ("other",), "zh": ("other",), "ko": ("other",), "th": ("other",), "vi": ("other",),
}
SFX_RE = re.compile(r"^(?P<stem>.*)\.(?P<cat>zero|one|two|few|many|other)$")
ICU_RE = re.compile(r"\{([A-Za-z_][\w]*)\s*,\s*plural\s*,")
# a category clause:  other {..}  or  =0 {..}  or  one{..}
CLAUSE_RE = re.compile(r"(?:^|\s)(=?\d+|[a-z]+)(?:\s*)\{", re.I)


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def load_csv(path):
    rows, cols = gst_read.load_loc_csv(path)
    if not rows:
        raise GstInputError("%s: empty CSV" % path)
    return rows, cols


def lang_columns(cols, key_col, source, langs):
    skip = {key_col, "comment", "notes", "context", "description"}
    if langs:
        return [x.strip() for x in langs.split(",") if x.strip()]
    out = []
    for c in cols:
        if c == key_col or c in skip:
            continue
        out.append(c)
    if source and source not in out and source in cols:
        out = [source] + [c for c in out if c != source]
    return out


def icu_categories(text):
    """Return a list of (var, set_of_cats) for each plural block, or [] if none."""
    found = []
    for m in ICU_RE.finditer(text or ""):
        start = m.end()
        # scan until the matching closer of the outer { that started at m.start()
        depth, i = 1, m.start()
        # m.start is the '{'; we already know depth 1; find end of this message
        i = m.start() + 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[m.end(): i - 1] if i else text[m.end():]
        cats = set()
        # walk clauses at depth 0 of the body
        pos, d = 0, 0
        tok = ""
        while pos < len(body):
            ch = body[pos]
            if ch == "{":
                if d == 0:
                    name = tok.strip()
                    if name.startswith("="):
                        cats.add(name)
                    elif (name or '').lower() in CATS:
                        cats.add((name or '').lower())
                    tok = ""
                d += 1
            elif ch == "}":
                d = max(0, d - 1)
                if d == 0:
                    tok = ""
            elif d == 0:
                tok += ch
            pos += 1
        found.append((m.group(1), cats, body))
    return found


def issues_for_text(key, lang, row, text, source_text, required):
    out = []
    blocks = icu_categories(text)
    src_blocks = icu_categories(source_text) if source_text is not None else []
    if src_blocks and not blocks and (text or "").strip():
        out.append({"key": key, "lang": lang, "row": row, "issue": "missing-icu-plural",
                    "detail": "source has an ICU plural but this language does not"})
    for var, cats, _body in blocks:
        if "other" not in cats:
            out.append({"key": key, "lang": lang, "row": row, "issue": "icu-missing-other",
                        "detail": f"{{{var}, plural, ...}} has no 'other' (have: {', '.join(sorted(cats)) or 'none'})"})
        missing = [c for c in required if c not in cats and c != "other"]
        # 'other' already handled; required may include other
        missing = [c for c in required if c not in cats]
        if missing:
            out.append({"key": key, "lang": lang, "row": row, "issue": "icu-missing-category",
                        "detail": f"{{{var}, plural}} missing {', '.join(missing)}"})
    return out


def suffix_families(rows, key_col):
    families = {}  # stem -> {cat: (row_index, key, rowdict)}
    bare = {}
    for i, r in enumerate(rows, 2):
        key = (r.get(key_col) or "").strip()
        if not key:
            continue
        m = SFX_RE.match(key)
        if m:
            stem, cat = m.group("stem"), m.group("cat")
            families.setdefault(stem, {})[cat] = (i, key, r)
        else:
            bare[key] = (i, key, r)
    return families, bare


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check ICU / suffix plural forms across language columns.")
    ap.add_argument("csv")
    ap.add_argument("--source", default="en", help="source language column (default: en)")
    ap.add_argument("--langs", help="comma list of language columns (default: every non-key column)")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--require", help="comma list of extra categories every ICU plural must include (besides other)")
    ap.add_argument("--no-lang-cats", action="store_true",
                    help="do not require CLDR categories for a language column (only 'other' is required)")
    ap.add_argument("-o", "--out", help="write the report (json if the path ends in .json, else text)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--no-fail", action="store_true", help="exit 0 even when issues are found")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.out:
        safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    rows, cols = load_csv(a.csv)
    if a.key not in cols:
        sys.exit(f"key column {a.key!r} not in CSV")
    if a.source not in cols:
        sys.exit(f"source column {a.source!r} not in CSV")
    langs = lang_columns(cols, a.key, a.source, a.langs)
    extra = [c.strip() for c in (a.require or "").split(",") if c.strip()]
    issues = []

    # per-cell ICU
    for i, r in enumerate(rows, 2):
        key = (r.get(a.key) or "").strip()
        if not key:
            continue
        src = r.get(a.source) or ""
        for lang in langs:
            text = r.get(lang) or ""
            required = ["other"]
            if not a.no_lang_cats:
                required = list(LANG_CATS.get((lang or '').lower(), LANG_CATS.get((lang or '').split("-")[0].lower(), ("other",))))
            for c in extra:
                if c not in required:
                    required.append(c)
            issues.extend(issues_for_text(key, lang, i, text, src if lang != a.source else None, required))

    # suffix families
    families, bare = suffix_families(rows, a.key)
    for stem, cats in families.items():
        # family must have .other (or a bare stem used as other)
        if "other" not in cats and stem not in bare:
            sample = next(iter(cats.values()))
            issues.append({"key": stem, "lang": "*", "row": sample[0], "issue": "suffix-missing-other",
                           "detail": f"family {stem}.* has {', '.join(sorted(cats))} but no .other"})
        # each language: if any suffix in the family has a value, required cats should too
        for lang in langs:
            required = ["other"]
            if not a.no_lang_cats:
                required = list(LANG_CATS.get((lang or '').lower(), LANG_CATS.get((lang or '').split("-")[0].lower(), ("other",))))
            present = {}
            for cat, (_i, _k, row) in cats.items():
                if (row.get(lang) or "").strip():
                    present[cat] = True
            if stem in bare and (bare[stem][2].get(lang) or "").strip():
                present.setdefault("other", True)
            if not present:
                continue  # nothing in this language — loc-missing's job
            for cat in required:
                if cat not in present:
                    issues.append({"key": stem, "lang": lang, "row": next(iter(cats.values()))[0],
                                   "issue": "suffix-missing-category",
                                   "detail": f"{stem}.{cat} empty or missing for {lang}"})

    fmt = a.format
    if a.out and a.out.lower().endswith(".json"):
        fmt = "json"
    lines = [f"{x['issue']}  {x['key']}  {x['lang']}  row {x['row']}  {x['detail']}" for x in issues]
    text = ("\n".join(lines) + ("\n" if lines else "")) or "no plural issues\n"
    print(text, end="")
    rec = {"issues": issues, "count": len(issues)}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        if fmt == "json":
            json.dump(rec, open(a.out, "w"), indent=1)
        else:
            open(a.out, "w", encoding="utf-8").write(text)
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0 if (not issues or a.no_fail) else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
