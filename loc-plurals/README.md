# loc-plurals

Check ICU `{var, plural, one {...} other {...}}` messages and gettext-style key suffixes (`.zero` / `.one` / `.two` / `.few` / `.many` / `.other`) across language columns of a loc CSV. Every ICU plural must include `other`. Suffix families must include `.other` (a bare stem counts as other). By default each language column is also expected to include its usual CLDR cardinal categories (en: one+other; pl: one+few+many+other; ja: other only). Exits 1 when issues are found; `--no-fail` is report-only.

```
gst loc-plurals loc.csv
gst loc-plurals loc.csv --source en --langs fr,de -o plurals.json --no-fail
```

## Usage

```bash
python3 loc-plurals/loc_plurals.py loc.csv
python3 loc-plurals/loc_plurals.py loc.csv --source en --langs fr,de -o plurals.json --no-fail
```

Run `python3 loc-plurals/loc_plurals.py --help` (or `gst loc-plurals --help`) for every option. Requires Python 3.10+.

## Known gaps

Nested/select-ordinal ICU and offset clauses are only scanned for category names, not semantically validated. CLDR coverage is a small built-in table, not the full CLDR chart. Exact-count `=0` / `=1` clauses do not substitute for named categories.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
