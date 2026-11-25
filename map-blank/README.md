# map-blank

Write an empty finite orthogonal Tiled JSON map of a given size. `--size WxH` is the map in tiles; `--tile N` or `--tile WxH` is the tile size (default 16). `--layers` is a comma-separated list of empty tile layer names (default: ground). Optional `--tileset` adds a tileset reference. There is no input file; `-o` is required.

## Usage

```bash
python3 map-blank/map_blank.py -o empty.json --size 32x12 --tile 16 --pretty
python3 map-blank/map_blank.py -o empty.json --size 16x16 --layers ground,fg --tileset tiles.png --tilecount 8 --columns 8
```

Run `python3 map-blank/map_blank.py --help` (or `gst map-blank --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Orthogonal finite maps only (no infinite/chunked output, no isometric). Layer data is a plain JSON array of zeros. This does not paint a level (use map-fill / map-stamp / a bake script).

## Tests

`python3 -m pytest -q tests/test_batch28.py`
