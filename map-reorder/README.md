# map-reorder

Reorder Tiled JSON layers (and optionally objects inside a named layer) from a name list or a one-name-per-line file, writing a new map. Unlisted sibling layers keep their relative order at the end. Group children can be targeted with a `group/child` path. `--tiles-first` / `--objects-last` shuffle top-level layers by type. Encoded tile data is decoded. The input is never overwritten.

## Usage

```bash
python3 map-reorder/map_reorder.py level.json -o ordered.json --order fg,ground,fx/smoke --objects mobs:player,door
python3 map-reorder/map_reorder.py level.json -o ordered.json --tiles-first --objects-last
```

Run `python3 map-reorder/map_reorder.py --help` (or `gst map-reorder --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-clean, map-merge and tmx-objects-csv.

## Source and licence

Original code. Layers are matched by name, not id; duplicate names are moved together. Missing names are reported but are not an error.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
