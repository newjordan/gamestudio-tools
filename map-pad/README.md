# map-pad

Grow a finite orthogonal Tiled JSON map with empty border tiles. `--margin N` pads every side, or `--pad LEFT,TOP,RIGHT,BOTTOM` sets each side in tiles. Objects and image layers are shifted by the left/top padding in pixels. The inverse of map-crop (without a used-tile shrink). Encoded layers are decoded first. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 map-pad/map_pad.py room.json -o room_pad.json --margin 2
python3 map-pad/map_pad.py room.json -o room_pad.json --pad 1,0,1,2
```

Run `python3 map-pad/map_pad.py --help` (or `gst map-pad --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Orthogonal finite JSON maps only. New cells are GID 0. Group layers are walked. Infinite / chunked maps are refused.

## Tests

`python3 -m pytest -q tests/test_batch27.py`
