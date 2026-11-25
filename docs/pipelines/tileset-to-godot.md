# Tileset generate, wang, Godot

Generate a 47-tile blob autotile sheet, write a Tiled tileset JSON with a wang set for terrain
painting, then emit a Godot 4 TileSet `.tres`. Godot itself is not opened.

## Tools

tileset-gen → tileset-wang → tileset-merge → tileset-split → godot-tileset

## Commands

```bash
mkdir -p /tmp/pipe-tileset
gst tileset-gen -o /tmp/pipe-tileset/grass --tile 8 --inner '#4a8f3c' --outer '#8a6a3f'
gst tileset-wang /tmp/pipe-tileset/grass.json -o /tmp/pipe-tileset/grass.tsj --pretty
gst godot-tileset /tmp/pipe-tileset/grass.tsj -o /tmp/pipe-tileset/grass.tres \
    --res res://art/grass.png
```

## Known gaps

godot-tileset emits physics collision polygons, terrain sets (from wangsets) and
compact-grid tile animations; modulated tiles are still not emitted. Official Godot
4.7.2.stable.official.ed1daf0bf loads those features (optional `GODOT_BIN` test).
The tileset-gen neighbour-bit convention differs from autotile-gen's 4-bit one; use
this tool's lookup (see the tileset-gen README). Ellipse colliders are a 12-gon;
`--colliders` is tileset-sheet space, not a level map. Animations that are not a
compact atlas grid are skipped.
