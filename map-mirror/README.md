# map-mirror

Mirror a Tiled orthogonal JSON map horizontally or vertically. Tile cells move with the layer and GID flip flags follow Tiled's `flipHorizontally` / `flipVertically` rules. Axis-aligned objects and polygon / polyline points are mirrored; tile-object GIDs are flipped the same way as cells. Two applications of the same axis are identity for cells, flags and axis-aligned objects.

## Usage

```bash
python3 map-mirror/map_mirror.py map.json -o mirror_h.json --axis h
```

Run `python3 map-mirror/map_mirror.py --help` (or `gst map-mirror --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Infinite, hexagonal, isometric and staggered maps are refused. Rotated rectangle objects are best-effort (origin and size use the axis-aligned box formula; rotation is negated). Ellipse / text / point objects and layer parallax are best-effort. Verify odd shapes in Tiled.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
