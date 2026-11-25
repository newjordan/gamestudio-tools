# loc-sort

Sort a loc CSV by the key column (stable), keep the header, and report duplicate keys. Exit 1 when duplicates are found, unless `--no-fail`.

## Usage

```bash
python3 loc-sort/loc_sort.py strings.csv -o strings_sorted.csv --json report.json
```

Run `python3 loc-sort/loc_sort.py --help` (or `gst loc-sort --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Sort is a plain Unicode string sort of the key column, not a natural / locale sort. Rows with an empty key are kept and sort first. Multi-line quoted CSV fields are handled by Python's csv module.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
