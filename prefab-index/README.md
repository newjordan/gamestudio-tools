# prefab-index

Walk a folder of Tiled JSON maps and write a CSV or JSON index of each file: name, size, tilesets, layer names, object types and counts, and custom map properties. Useful as a catalogue of prefab rooms. Encoded tile data is not required (only metadata is read).

## Usage

```bash
python3 prefab-index/prefab_index.py prefabs/ -o prefabs.csv
python3 prefab-index/prefab_index.py prefabs/ -o prefabs.json --json
```

JSON is also chosen when `-o` ends in `.json`. Files without a `layers` key are skipped. Run `python3 prefab-index/prefab_index.py --help` (or `gst prefab-index --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements tilemap-stats, room-graph and tmx-objects-csv.

## Source and licence

Original code. Nested group layers are flattened into the layer-name list. Object types fall back to Tiled's `class` field when `type` is empty.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
