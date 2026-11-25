# loc-diff

Compare two localisation CSVs by key. Reports keys only in A or only in B, and cells that changed in shared language columns (matched by name). Exit 1 when anything differs unless `--no-fail`. Optional `--json` report and `--out` CSV of added, removed and changed rows. The inputs are never overwritten unless `--in-place`.

## Usage

```bash
python3 loc-diff/loc_diff.py old.csv new.csv --json diff.json
python3 loc-diff/loc_diff.py old.csv new.csv -o changes.csv --no-fail
```

Run `python3 loc-diff/loc_diff.py --help` (or `gst loc-diff --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only. A language column present in only one file is treated as empty on the other side. Duplicate keys inside one file are reported but the first row wins (same as loc-merge). This is a table diff, not a merge (use loc-merge for that).

## Tests

`python3 -m pytest -q tests/test_batch25.py`
