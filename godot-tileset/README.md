# godot-tileset

Write a Godot 4 TileSet `.tres` (text resource) from a Tiled tileset JSON / TSX, a tileset-gen / autotile-gen meta JSON, or a plain image with `--tile`. The texture path is written as `res://...` (override with `--res`).

Physics collision polygons are emitted from each tile's Tiled `objectgroup` (rectangle, ellipse as a 12-gon, polygon, closed polyline; `one_way` via a property or type) and from `--colliders`. `--colliders` accepts tile-colliders JSON in *tileset sheet space* (rects are split onto atlas tiles), a `{solid:[ids]}` list for full-tile boxes, or `{tiles:{id:{rects|polygons|objectgroup}}}`. A *level* map collider file will not map cleanly onto a tileset sheet. Terrain sets come from embedded `wangsets` or `--wang` (tileset-wang / Tiled wangsets). Tiled colour indices are 1-based and become Godot terrains 0-based; wang type mixed / corner / edge maps to terrain-set mode 0 / 1 / 2. Tile animations are emitted when the frame `tileid`s form a compact atlas grid (row, column, or rectangle); otherwise a warning is printed and that animation is skipped. Mid-animation atlas cells are reserved and are not also emitted as standalone tiles. `--no-collision`, `--no-terrain`, and `--no-animation` drop each feature. Optional `--json` report. The input is never overwritten unless `--in-place`. Godot itself is not opened by this tool.

## Usage

```bash
python3 godot-tileset/godot_tileset.py grass.tsj -o grass.tres --res res://art/grass.png
python3 godot-tileset/godot_tileset.py tiles.png -o tiles.tres --tile 16
python3 godot-tileset/godot_tileset.py water.tsj -o water.tres --colliders col.json --wang wang.tsj --res res://art/water.png
```

Run `python3 godot-tileset/godot_tileset.py --help` (or `gst godot-tileset --help`) for every option. Requires Python 3.10+ (Pillow when the image must be measured).

## Inspiration (catalogue entry)

None (new). Complements godot-import-presets, tileset-wang, tile-colliders and atlas-to-godot.

## Source and licence

Original code from the documented Godot 4 text-resource layout, checked against a live editor-saved TileSet in official Godot 4.7.2.stable.official.ed1daf0bf. Physics polygons are in tile-centre space (y down). Animation frame time is `duration_ms/1000 * animation_speed` seconds with `animation_speed = 10`. Collision, terrain sets / peering bits, and compact-grid animations were loaded in that same official binary (`GODOT_BIN` integration test). Tiled animations whose frames do not form a compact atlas grid are skipped. Ellipse colliders are approximated as a 12-gon. Objectgroup open polylines are ignored.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
