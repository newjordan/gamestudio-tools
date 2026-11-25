# game-data-lint

Validate item/enemy/quest data tables (CSV or JSON) against a small schema: types, min/max, enums, regex, unique keys, required fields and cross-table references, plus warnings for fields the schema does not know (typos).

## Usage

```bash
python3 game-data-lint/game_data_lint.py data/schema.json --strict --json report.json
```

Run `python3 game-data-lint/game_data_lint.py --help` (or `gst game-data-lint --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

MasterMemory (typed, validated data tables).

## Source and licence

Original code; no code from MasterMemory. The schema format is documented at the top of the script.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
