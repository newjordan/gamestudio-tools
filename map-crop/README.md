# map-crop

Crop a Tiled JSON map to the bounding box of used tiles (and optionally objects), plus a tile margin, rewriting layer data and shifting objects so they stay aligned. Encoded tile data is decoded. Infinite maps: chunks outside the crop are dropped and remaining chunks are shifted. The input is never overwritten.

## Usage

```bash
python3 map-crop/map_crop.py level.json -o cropped.json --margin 2 --pretty --json crop.json
python3 map-crop/map_crop.py level.json -o cropped.json --tiles-only
```

Run `python3 map-crop/map_crop.py --help` (or `gst map-crop --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-clean and map-merge.

## Source and licence

Original code. Finite maps are clamped to the original bounds; a completely empty map keeps a 1x1 canvas at the origin. Image-layer offsets are shifted but the image itself is not cropped.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
