# tile-replace

Remap GIDs in a Tiled JSON map from a JSON or CSV table (after tile-dedupe, or a manual swap list). Flip flags are kept. Tile-layer cells and object `gid`s are rewritten. Unmapped GIDs are left alone unless `--unmapped 0` (clear the cell) is set. Encoded tile data is decoded. Writes a new map; the input is never overwritten.

## Usage

```bash
python3 tile-replace/tile_replace.py level.json --remap remap.json -o level2.json --pretty --json report.json
python3 tile-replace/tile_replace.py level.json --remap remap.csv -o level2.json --unmapped 0
```

The remap table may be a JSON object (`{"1": 5, "2": 6}`), a JSON list of `{from,to}`, a `{remap: {...}}` wrapper, or a CSV with `from,to` (aliases: `old,new`). Run `python3 tile-replace/tile_replace.py --help` (or `gst tile-replace --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements tile-dedupe, map-clean and map-diff.

## Source and licence

Original code. Uses the shared tile-data decoder in map-diff. Infinite-map chunks are remapped in place. Tileset `firstgid`s are not rewritten (the table is the whole mapping).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
