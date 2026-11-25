# loc-split

Split a multi-language localisation CSV into per-language files (`{stem}_{lang}.csv` with the key column plus that language). The inverse of a later loc-join. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 loc-split/loc_split.py strings.csv --outdir langs/
```

Run `python3 loc-split/loc_split.py --help` (or `gst loc-split --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

One file per language column; the key column is copied into each. Duplicate source keys are first-wins (same as loc-merge) and listed in the JSON. Empty language cells are written as empty strings. Not a gettext/PO split (use loc-convert for that).

## Tests

`python3 -m pytest -q tests/test_batch27.py`
