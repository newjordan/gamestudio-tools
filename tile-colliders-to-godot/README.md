# tile-colliders-to-godot

Write a Godot 4 StaticBody2D scene from tile-colliders JSON (or a Tiled object-layer rectangle list). Each rectangle becomes a CollisionShape2D at the rectangle centre.

## Usage

```bash
python3 tile-colliders-to-godot/tile_colliders_to_godot.py level.colliders.json -o level_body.tscn
```

Run `python3 tile-colliders-to-godot/tile-colliders-to-godot.py --help` (or `gst tile-colliders-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only axis-aligned rectangles are emitted. Zero-size rects are skipped. Polygon / ellipse Tiled objects in the objects list are treated as their width/height box.

## Tests

`python3 -m pytest -q tests/test_batch32.py`
