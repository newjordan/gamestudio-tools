# map-fill

Rectangle-fill or 4-connected flood-fill cells on a Tiled tile layer. `--only-gid` limits a rectangle fill to cells that already have that unmasked GID. Encoded data is decoded.

## Usage

```bash
python3 map-fill/map_fill.py map.json -o filled.json --layer ground --rect 2,2,4,3 --gid 7
python3 map-fill/map_fill.py map.json -o pond.json --flood 10,8 --gid 3
```

Run `python3 map-fill/map_fill.py --help` (or `gst map-fill --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Infinite maps are refused (run tmx-infinite-to-finite first). Flood fill is 4-connected only. Diagonal connectivity and pattern-based fills are out of scope. Existing flip flags are kept on replaced cells unless `--gid` itself carries flags.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
