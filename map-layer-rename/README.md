# map-layer-rename

Regex-rename Tiled JSON layer names, and optionally object names, by `--pattern` / `--repl`. `--targets layers,objects` picks what is rewritten. `--dry-run` prints the planned changes and writes nothing. Writes a new map; the input is never overwritten.

## Usage

```bash
python3 map-layer-rename/map_layer_rename.py level.json --pattern '^fg_' --repl 'front_' -o level2.json --pretty
python3 map-layer-rename/map_layer_rename.py level.json --pattern 'Spn' --repl 'Spawn' --targets objects --dry-run
```

Run `python3 map-layer-rename/map_layer_rename.py --help` (or `gst map-layer-rename --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-reorder, tmx-props-lint and prefab-index.

## Source and licence

Original code. Group layers are walked recursively. The regex is Python's `re.sub` (group backrefs such as `\1` work).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
