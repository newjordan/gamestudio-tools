# map-layer-split

Split a Tiled JSON tile layer into one layer per tileset, by GID range (`firstgid` .. `firstgid+tilecount`). Flip flags are kept. GIDs that match no tileset go on an `unassigned` layer unless `--no-leftover`. Encoded tile data is decoded.

## Usage

```bash
python3 map-layer-split/map_layer_split.py level.json -o split.json --layer ground --drop-source --pretty
```

Run `python3 map-layer-split/map_layer_split.py --help` (or `gst map-layer-split --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Infinite maps are refused. Nested group layers are located by name at the top level when splicing the new layers in.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
