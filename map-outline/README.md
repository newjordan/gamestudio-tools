# map-outline

Find the 4-connected outline of solid cells on a finite orthogonal Tiled JSON map, using the same walkability as map-reach. Writes an optional JSON report, a PNG overlay, and/or a copy of the map with an `outline` tile layer.

## Usage

```bash
python3 map-outline/map_outline.py maps/cave.json --json outline.json --png outline.png -o cave_outline.json --solid-layer walls
```

Run `python3 map-outline/map_outline.py --help` (or `gst map-outline --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Finite orthogonal maps only. The outline is 4-connected (no diagonal-only neighbours) and includes solid cells on the map edge. The PNG is a walkability overlay, not a tileset render. The optional outline layer is a new tile layer; existing layers are not edited.

## Tests

`python3 -m pytest -q tests/test_batch30.py`
