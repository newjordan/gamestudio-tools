# loc-icu-extract

Pull ICU `{var, plural, ...}` message forms and gettext-style key suffixes out of a loc CSV into a review table (CSV or JSON), including the categories present and the ones the language still needs.

## Usage

```bash
python3 loc-icu-extract/loc_icu_extract.py strings.csv -o review.csv
```

Run `python3 loc-icu-extract/loc_icu_extract.py --help` (or `gst loc-icu-extract --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Select / choice ICU forms are not extracted (plurals only). CLDR category lists are the same compact table as loc-plurals (not a full CLDR dataset). Very large nested ICU messages are scanned by brace depth, not a full parser.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
