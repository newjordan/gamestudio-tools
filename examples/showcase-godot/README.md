# GST Showcase (Godot 4.7)

A minimal top-down Godot 4.7 project whose every runtime asset is produced by
the gamestudio-tools kit from procedural generators. Nothing in `art/`, `sfx/`,
`font/` or `preview/` is hand-painted or recorded.

## Scene

- A `TileMapLayer` of grass/dirt blob autotiles, with terrain peering and
  physics polygons on solid wall tiles.
- A `CharacterBody2D` player with a 3-frame `SpriteFrames` walk clip.
- A step SFX (`AudioStreamPlayer`) when the player enters a new cell.
- A HUD `Label` in a BMFont baked from Pillow's bundled default face (no
  vendored TTF).

Move with the arrow keys / WASD (`ui_*` actions) in the editor. Gravity is off;
the body uses floating motion.

## Regenerate assets

From this directory, with `gst` on `PATH` or this folder still sitting inside a
kit checkout:

```bash
./build_showcase.sh
```

The script wipes generated outputs and rebuilds them with:

`tex-gen`, `tileset-gen`, `tileset-wang`, `tile-colliders`, `godot-tileset`,
`dungeon-gen`, `pixelize`, `sprite-outline-gen`, `sprite-canvas`,
`sprite-shadow`, `anim-from-folder`, `atlas-pack`, `atlas-to-godot`, `sfx-gen`,
`sfx-normalize`, `wav-loud-apply`, `bmfont-gen`, `godot-import-presets`, and
(when `GODOT_BIN` can render) `frames-to-sheet` + `spritesheet-gif` + `gif-optimize`.

`bake_map.py` and `stamp_tile.py` (this folder) map the dungeon through the tileset-gen neighbour
`lookup` into `art/cells.json`. The main scene loads that JSON at runtime and
calls `TileMapLayer.set_cell`. Wall cells always use atlas tile 47 (a solid dirt tile stamped into the empty
slot of the 8×6 blob sheet) so tileset physics can stop the player. Blob tile 0
is an isolated grass cap, not a full wall.

## Integration test

`tests/test_showcase_godot.py` (in the kit) runs the build, then — when
`GODOT_BIN` points at a Godot 4 editor — imports the project headless and runs
the main scene with `-- --verify`. A script walks the player into a wall for 30
physics frames, asserts they did not enter the wall cell, and prints
`GST_SHOWCASE_OK`.

Official verification: Godot 4.7.2 (`4.7.2.stable.official.ed1daf0bf`). The
official Godot editor binary is not in the kit tarball; set GODOT_BIN to a Godot 4.7.2 editor.

```bash
export GODOT_BIN=/path/to/Godot_v4.7.2-stable_linux.x86_64
./build_showcase.sh
"$GODOT_BIN" --headless --path . --import --quit
"$GODOT_BIN" --headless --path . -- --verify
```

## Preview GIF

When `GODOT_BIN` and a display (or `xvfb-run`) are available, the build also
runs the scene with a software GL renderer (`LIBGL_ALWAYS_SOFTWARE=1`,
`gl_compatibility`) and `--write-movie`, then packs a short GIF with the kit:

- `preview/shot_08.png`, `preview/shot_16.png`, `preview/shot_24.png`
- `preview/showcase.gif`

`--headless` uses the dummy renderer and cannot be used for these frames.

## Licence

No licence has been applied to the kit or to this example yet.
