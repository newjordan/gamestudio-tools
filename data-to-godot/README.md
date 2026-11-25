# data-to-godot

Write a Godot 4 Resource `.tres` plus a small script from a CSV or JSON game table. The script exports `columns` and `rows` (an array of dictionaries) so designers can load item/stat tables without a custom importer.

## Usage

```bash
python3 data-to-godot/data_to_godot.py items.csv -o items.tres --res res://data/ --json report.json
```

Run `python3 data-to-godot/data_to_godot.py --help` (or `gst data-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

No typed Resource subclass beyond Array[Dictionary] (every cell is inferred as int, float, bool or string). A `{id: object}` JSON map always stores the key as `id`. ICU / plural loc columns are not special-cased. The companion `.gd` must sit at the `--res` path inside a Godot project.

## Tests

`python3 -m pytest -q tests/test_batch32.py`
