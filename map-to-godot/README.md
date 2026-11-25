# map-to-godot

Write a Godot 4.x TileMapLayer `.tscn` from a Tiled JSON or TMX map. `tile_map_data` uses the packed-byte layout from official Godot 4.7.2 (format 0, then per cell x, y, source_id, atlas_x, atlas_y, alternative_tile). Optional `--write-tileset` also writes a TileSet `.tres`. Tiled H/V/diagonal flip flags become TileSetAtlasSource alternative tiles (`flip_h` / `flip_v` / `transpose`) with a stable alternative id (bit 0 = H, bit 1 = V, bit 2 = diagonal).

## Usage

```bash
python3 map-to-godot/map_to_godot.py level.json -o level.tscn --write-tileset level_tileset.tres --cells-json cells.json --json report.json
```

Run `python3 map-to-godot/map_to_godot.py --help` (or `gst map-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new). Fills the Tiled-to-Godot scene gap that was dropped in batch 4 because the tile payload could not be verified without a Godot editor.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Object layers are listed in `--json` but not turned into nodes (use map-objects-to-godot). Finite orthogonal maps only. Flipped GIDs require `--write-tileset` (or a TileSet that already defines the same alternative ids) or Godot will draw the base tile. Tiled's four remaining rotate/flip bits (hex 0x10000000) are ignored.
