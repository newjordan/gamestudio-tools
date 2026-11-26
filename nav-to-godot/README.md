# nav-to-godot

Write a Godot 4 NavigationRegion2D scene from a Tiled map's walkability (same rules as map-reach / nav-grid). Walkable tiles are merged into rectangles and written as NavigationPolygon outlines in pixel coordinates.

## Usage

```bash
python3 nav-to-godot/nav_to_godot.py level.json -o level_nav.tscn --json report.json

# solids from tile-colliders output, the project's usual pipeline
python3 tile-colliders/tile_colliders.py level.json -o level.colliders.json
python3 nav-to-godot/nav_to_godot.py level.json -o level_nav.tscn      # picks level.colliders.json up by itself
```

### Where the solids come from

1. `--solid-layer` / `--solid-ids` (the map-reach rules) are used when you give them. Giving either one means you chose the solids, so no sibling file is picked up automatically.
2. `--colliders FILE` is a tile-colliders output (the default `rects` JSON, or the `--tiled-objects` object layer). A cell a rectangle covers completely is solid; a cell it covers only in part is **cut**: the rectangle is subtracted from the cell exactly (the cell is split along the collider edges and the free boxes are merged back into axis-aligned rectangles), so a half-tile wall leaves the other half walkable. Those cut pieces are then merged with neighbouring walkable rectangles that share a full edge, so a half-tile wall does not leave a strip of small leftover polygons. It is combined with `--solid-layer` / `--solid-ids` / `--ground-layer` when those are given as well.
3. With none of the above, nav-to-godot looks next to the map for `<map stem>.colliders.json`, `<map stem>_colliders.json` or `<map stem>-colliders.json` (first one found) and uses it. That is "the same project": the same folder as the map. A file for a different tile size, or one that is not tile-colliders output, is an error rather than silently ignored.
4. `--no-colliders` turns step 3 off. With nothing at all, every tile is walkable.

The `--json` report records `colliders` (the file used) and `colliders_source` (`flag`, `auto` or null), plus `cut_cells`, `cut_pieces`, `blocked_cells`, `dropped_slivers`, `overflow_cells`, `rects_before_merge` and `merged`. `walkable` counts only the cells no collider touched; `rects` is the number of outlines after the neighbouring-cell merge.

### Cutting rules (what is and is not robust)

- Exact for axis-aligned rectangles: every walkable point is covered by exactly one output rectangle and none lies inside a collider (checked by a randomised test and in Godot 4.7.2). Collider edges that sit exactly on a cell edge do not cut.
- `--min-piece PX` (default 1) drops free pieces thinner than PX pixels, so a 0.5 px strip beside a wall is treated as blocked. `--min-piece 0` keeps everything.
- A cell crossed by more than 64 colliders is blocked whole (`overflow_cells`) instead of cut, to keep the output bounded.
- `--block-whole-cells` restores the 2.1.0 behaviour (any overlap blocks the whole cell).
- Only rectangles are cut. Rotated or polygonal colliders are not read at all.

Run `python3 nav-to-godot/nav-to-godot.py --help` (or `gst nav-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

Since 2.5.0 all polygons share one welded vertex list and every rectangle corner that lies inside another
rectangle's side is inserted into that side. Godot links navigation polygons only across identical edges, so in
2.4.0 rooms that met a corridor at a T-junction were separate islands and `map_get_path` returned an empty path.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Adjacent output rectangles that share a full edge are merged, including cut pieces with neighbouring cells. A generic `colliders.json` is not auto-detected, only the map-stem names above. Finite orthogonal walking only (no jump arcs or one-way tiles). Regions are axis-aligned unions, not a tight outline of irregular caves. Godot still needs to bake the navmesh in the editor or at runtime if the project requires it.

## Tests

`python3 -m pytest -q tests/test_batch32.py tests/test_v21.py tests/test_v22.py tests/test_v23.py`
