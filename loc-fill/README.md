# loc-fill

Fill empty cells in a localisation CSV from a source-language column (default `en`). Non-empty target cells are left alone unless `--overwrite`. Optional `--prefix` is prepended to filled values. First-wins on duplicate keys.

## Usage

```bash
python3 loc-fill/loc_fill.py strings.csv -o filled.csv --source en --json report.json
```

Run `python3 loc-fill/loc_fill.py --help` (or `gst loc-fill --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only. Duplicate keys after the first are kept in the output file (row order preserved) but do not get a second fill pass from the first-wins row. There is no ICU/plural awareness.

## Tests

`python3 -m pytest -q tests/test_batch30.py`
