# loc-merge

Combine two localisation CSVs by key. Language columns are unioned (A's order first, then any new columns from B). Keys present in only one file are kept and listed as missing. When the same key has different values in a shared language, `--prefer a|b` picks a side (default `a`) and the run exits 1 unless `--no-fail`. `--prefer fail` refuses to write when any collision is present. Inputs are never overwritten unless `--in-place`.

## Usage

```bash
python3 loc-merge/loc_merge.py en.csv fr.csv -o strings.csv --json report.json
python3 loc-merge/loc_merge.py a.csv b.csv -o merged.csv --prefer b --no-fail
```

Run `python3 loc-merge/loc_merge.py --help` (or `gst loc-merge --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only (not PO / JSON dictionaries). Duplicate keys within one file keep the first row and are reported. Blank keys are skipped. `--prefer fail` exits without writing the merged CSV; the JSON report is still written if requested.

## Tests

`python3 -m pytest -q tests/test_batch24.py`
