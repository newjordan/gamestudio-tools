# map-layer-merge

Flatten named tile layers of a Tiled JSON map into one layer. Later layers overwrite earlier non-empty cells; flip flags on the GID are kept. Object layers and unmentioned tile layers pass through. Encoded tile data is decoded to a plain array. `--drop-sources` removes the layers that were merged.

```
gst map-layer-merge level.json -o flat.json --layers ground,deco --name ground --drop-sources --pretty
```

## Usage

```bash
python3 map-layer-merge/map_layer_merge.py level.json -o flat.json --layers ground,deco --name ground --drop-sources --pretty
```

Run `python3 map-layer-merge/map_layer_merge.py --help` (or `gst map-layer-merge --help`) for every option. Requires Python 3.10+.

## Known gaps

Infinite (chunked) maps are refused. Group-nested sources are merged but the merged layer is inserted at the top-level index of the first match.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
