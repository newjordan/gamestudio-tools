# tmx-objects-csv

Export Tiled object layers to a CSV, and optionally apply a CSV back onto a map. Export columns: map, layer, id, name, type, x, y, width, height, rotation, gid, visible, plus one column per custom property. `--import-csv` updates rows whose id already exists on the named layer and appends new ids (or a blank id). Refuses to overwrite the map on import. Group-layer paths use a slash, as in map-diff.

## Usage

```bash
python3 tmx-objects-csv/tmx_objects_csv.py maps/*.json -o objects.csv
python3 tmx-objects-csv/tmx_objects_csv.py maps/cave.json --import-csv objects.csv -o maps/cave_edited.json --pretty
```

Run `python3 tmx-objects-csv/tmx_objects_csv.py --help` (or `gst tmx-objects-csv --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements ldtk-to-csv (LDtk entities) and room-graph (door connections).

## Source and licence

Original code. Import requires that the named object layer already exists on the map; it will not create a missing layer.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
