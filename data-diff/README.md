# data-diff

Balance-review diff of two data tables (CSV or JSON, matched by a key column): added, removed and changed rows, field-level old to new with percent change, filters, Markdown or JSON output and CI exit codes.

## Usage

```bash
python3 data-diff/data_diff.py items_v1.csv items_v2.csv --key id --ignore description --min-pct 5 --md changes.md --fail-on-removed
```

Run `python3 data-diff/data_diff.py --help` (or `gst data-diff --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

MasterMemory (typed, validated game data tables).

## Source and licence

Original code; reuses game-data-lint's table loader.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
