# map-path

Find a walkable path on a finite orthogonal Tiled JSON map with A*. Walkability matches map-reach (solid / ground layers and solid ids). Optional JSON report and PNG overlay. Diagonal moves do not cut corners.

## Usage

```bash
python3 map-path/map_path.py maps/cave.json --start 2,4 --goal 10,4 --json path.json --png path.png --fail-if-none
```

Run `python3 map-path/map_path.py --help` (or `gst map-path --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Finite orthogonal maps with decoded array data only (map-diff.decode_map is used). Top-down 4/8-connected walking; no jump arcs, no one-way tiles, no costs besides ortho=10 and diagonal=14. The PNG is a walkability overlay, not a tileset render.

## Tests

`python3 -m pytest -q tests/test_batch29.py`
