# map-objects-to-godot

Write a Godot 4 Node2D scene from Tiled object layers. Points become Marker2D nodes; rectangles, ellipses and polygons become Area2D (or StaticBody2D with `--static`) with collision shapes. Custom properties and the Tiled type are stored as metadata.

Tile objects (objects with a `gid`) become a `Sprite2D` with `region_enabled` and the tileset cell as `region_rect`, `centered = false`, and the tileset image as an ExtResource. Tiled's horizontal, vertical and diagonal flip flags are decomposed into `flip_h`, `flip_v`, `rotation` and `scale` (a diagonal flip is `flip_v` plus a quarter turn), applied in Tiled's order (diagonal, then horizontal, then vertical). Object width and height scale the tile, `rotation` turns it about the object's anchor, and the tileset's `tileoffset` and `objectalignment` are honoured. Animated tiles (a tile with an `animation` list, from the map JSON, an external `.tsx` or an external `.tj`/JSON tileset) become an `AnimatedSprite2D` whose `SpriteFrames` is built from `AtlasTexture` frames (one shared resource per animated tile, frame durations scaled to the greatest common divisor, `autoplay = "default"`, looping); `--no-animation` keeps a plain `Sprite2D` showing the first frame. External `.tsx` tilesets are parsed, including image-collection tilesets (`<tile><image>`, relative image paths resolved next to the `.tsx`) and `<tileoffset>`. A GID that does not fall inside any tileset, or `--no-sprites`, leaves a `Marker2D` that still carries the GID as metadata.

Isometric (diamond) maps are projected into screen space: Tiled stores isometric object coordinates in logical units (one tile is `tileheight` wide), so positions become `(tx - ty) * tw / 2 + map_height * tw / 2, (tx + ty) * th / 2`, and rectangles, ellipses, polygons and polylines become projected shapes. Staggered and hexagonal maps already store object coordinates as screen pixels (Tiled's hexagonal renderer inherits the orthogonal identity for pixel-to-screen), so objects and axis-aligned shapes land where Tiled draws them; applying the diamond formula would put them in the wrong place. `Projection.tile_to_screen` maps *tile* coordinates the same way Tiled does, honouring `staggeraxis`, `staggerindex` and `hexsidelength`, and those fields are stored as metadata on the scene root. Polylines become a `Line2D` (`closed = false`, width from `--line-width`, default 2) plus a `CollisionPolygon2D` with `build_mode = 1` (segments — Godot has no dedicated polyline collider).

## Usage

```bash
python3 map-objects-to-godot/map_objects_to_godot.py level.json -o objects.tscn --json report.json

# put the tileset textures in a sub-folder of the Godot project
python3 map-objects-to-godot/map_objects_to_godot.py level.json -o objects.tscn --res res://art/
```

`--res` is the res:// folder that holds the tileset images (default `res://`); only the image file name is used. `--no-sprites` keeps tile objects as markers. The `--json` report lists `sprites`, `diagonal_sprites`, `unknown_gids`, `textures` and `orientation`.

Run `python3 map-objects-to-godot/map-objects-to-godot.py --help` (or `gst map-objects-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Animated tiles ignore Tiled's per-frame offsets (frames are assumed the same size; AnimatedSprite2D uses the first frame's size) and an animation that references a missing frame falls back to a still sprite. Tile *layers* are not touched by this tool (only objects). Isometric ellipses become 16-sided polygons. Ellipses that are not circles become capsules. Godot has no dedicated polyline collider: a polyline is a Line2D plus a CollisionPolygon2D in segment mode, which is an open chain of segments, not a filled polygon. Finite maps. metadata keys are sanitised to alphanumerics.

## Tests

`python3 -m pytest -q tests/test_batch32.py tests/test_v21.py tests/test_v22.py tests/test_v23.py`

The render test draws all eight flip combinations, a scaled diagonal flip and a rotated tile in official Godot under software GL (`xvfb-run`, set `GODOT_BIN`) and compares every pixel with a Pillow reference.
