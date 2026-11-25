# loc-join

Join per-language localisation CSVs into one multi-language table (the inverse of loc-split). Each input is `key + one or more language columns` (typically `{stem}_{lang}.csv`). Keys are the union of every file (missing cells stay empty). First-wins on duplicate keys inside a file. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 loc-join/loc_join.py langs/ -o strings.csv
python3 loc-join/loc_join.py strings_en.csv strings_fr.csv -o strings.csv --langs en,fr
```

Run `python3 loc-join/loc_join.py --help` (or `gst loc-join --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only. Language columns that appear in more than one file keep the first non-empty value. Column order follows the inputs unless `--langs` is set. This is not a three-way merge of already-wide tables (use loc-merge for that).

## Tests

`python3 -m pytest -q tests/test_batch28.py`
