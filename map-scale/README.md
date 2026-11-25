# map-scale

Scale a Tiled orthogonal finite map's tile size and pixel coordinates. `--factor` multiplies tilewidth / tileheight; `--tile W` or `--tile WxH` sets them absolutely (pass exactly one). Object positions and sizes, polygon / polyline points, layer offsets and image-layer positions are scaled by the same ratios so they stay aligned with the tiles. Tile GIDs and the map size in tiles are unchanged. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 map-scale/map_scale.py level.json -o level32.json --factor 2
python3 map-scale/map_scale.py level.json -o level32.json --tile 32x32
```

Run `python3 map-scale/map_scale.py --help` (or `gst map-scale --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Orthogonal finite maps only (hexagonal, isometric and infinite maps are refused). Tileset image files are not resampled — only the map's tile size and coordinates change. Tile layer data is left as a plain GID array (encoding keys are not rewritten; use tmx-encode).

## Tests

`python3 -m pytest -q tests/test_batch24.py`
