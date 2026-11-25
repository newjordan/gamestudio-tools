# nav-grid

Render a walkability grid (and optional BFS distance field) from a Tiled JSON map. Walkability follows map-reach (`--solid-layer`, `--ground-layer`, `--solid-ids`, `--diagonal`). Encoded tile data is decoded first. Pass `--start X,Y` or place a `spawn` / `start` / `player_start` object to flood and, with `--dist-csv`, write a CSV of distances (`-1` is blocked or unreached).

```
gst nav-grid level.json -o nav.png --solid-layer collision --start 2,3 --dist-csv dist.csv --scale 8
```

## Usage

```bash
python3 nav-grid/nav_grid.py level.json -o nav.png --solid-layer collision --start 2,3 --dist-csv dist.csv --scale 8
```

Run `python3 nav-grid/nav_grid.py --help` (or `gst nav-grid --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Known gaps

Infinite maps are refused (same as map-reach). The PNG is a preview, not a navmesh or Godot navigation polygon.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
