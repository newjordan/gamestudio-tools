# map-shift

Shift every tile and object on a finite orthogonal Tiled JSON map by a tile offset (`--tiles DX,DY`) and/or a pixel offset (`--pixels DX,DY`). Tiles that leave the map are dropped (vacated cells become 0) unless `--wrap` rolls them around. Objects are moved by the combined pixel delta and dropped when `--clip-objects` and their bbox leaves the map. Encoded layers are decoded first. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 map-shift/map_shift.py room.json -o room2.json --tiles 2,0
python3 map-shift/map_shift.py room.json -o room2.json --tiles 1,0 --wrap
```

Run `python3 map-shift/map_shift.py --help` (or `gst map-shift --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Orthogonal finite JSON maps only (decode a TMX first). `--pixels` does not slide the tile grid (tile data only moves by `--tiles`); it is added to the object / image-layer delta. Group layers are walked. Infinite / chunked maps are refused.

## Tests

`python3 -m pytest -q tests/test_batch26.py`
