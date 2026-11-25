# map-rotate

Rotate a Tiled orthogonal JSON map by 90, 180 or 270 degrees clockwise. Tile cells move with the layer (width and height swap on 90/270) and GID flip flags are updated so tiles stay visually aligned. Orthogonal rectangle objects are moved and rotated.

## Usage

```bash
python3 map-rotate/map_rotate.py map.json -o rot90.json --degrees 90
```

Run `python3 map-rotate/map_rotate.py --help` (or `gst map-rotate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Infinite, hexagonal, isometric and staggered maps are refused. Tile-object alignment, ellipse / text / point objects, and layer parallax or visual offsets other than offsetx/offsety are best-effort. Four times 90 degrees is identity for tile cells, flags and rectangle objects; verify odd shapes in Tiled.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
