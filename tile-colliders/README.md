# tile-colliders

Merge solid tiles of a Tiled-style map into the fewest axis-aligned rectangles (horizontal runs stacked vertically) and export JSON or a Tiled object layer. Far fewer physics shapes than one box per tile.

## Usage

```bash
python3 tile-colliders/tile_colliders.py level.json --solid 2 -o level_collision.json
python3 tile-colliders/tile_colliders.py level.json --solid 2,5,6 --tiled-objects -o collision_layer.json
```

Run `python3 tile-colliders/tile_colliders.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Tiled / LDtk level pipelines (collision layers).

## Source and licence

Original code. Greedy run merging is a standard approach, not guaranteed globally minimal.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
