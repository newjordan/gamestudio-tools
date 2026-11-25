# map-chunk

Split a finite orthogonal Tiled JSON map into a grid of smaller maps of `--size` tiles. Objects whose bounding box overlaps a chunk are copied and shifted into that chunk's local origin. Optional `--world` writes a Tiled `.world` index. Encoded tile data is decoded first. Infinite, isometric and hexagonal maps are refused. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 map-chunk/map_chunk.py overworld.json -o chunks/ --size 16x16 --world chunks/overworld.world
```

Run `python3 map-chunk/map_chunk.py --help` (or `gst map-chunk --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Orthogonal finite maps only. An object that straddles a chunk boundary is copied into every overlapping chunk (not clipped). Tile-objects, ellipse, text and point bounding boxes are best-effort. Image layers are shifted, not cropped.

## Tests

`python3 -m pytest -q tests/test_batch25.py`
