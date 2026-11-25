# Godot 4.7 showcase (all assets from kit generators)

A minimal top-down Godot 4.7 project under `examples/showcase-godot/`. Every runtime
asset is produced by procedural kit tools; `./build_showcase.sh` wipes and rebuilds
them. Official Godot 4.7.2 is used only to import, run a wall-collision verify, and
(when a display or xvfb is available) record a short preview GIF. The Godot binary
is not in the kit tarball.

## Tools

tex-gen → tileset-gen → (stamp a solid wall into the empty sheet slot) → tileset-wang →
godot-tileset (`--colliders`, `--wang`) → dungeon-gen → tile-colliders → bake_map.py
→ tex-gen / pixelize / sprite-outline-gen / sprite-canvas / sprite-shadow →
anim-from-folder → atlas-pack → atlas-to-godot → sfx-gen → sfx-normalize →
wav-loud-apply → bmfont-gen → godot-import-presets → (optional) frames-to-sheet →
spritesheet-gif → gif-optimize

## Commands

```bash
export GST_ROOT=/path/to/gamestudio-tools   # or run from a kit checkout
export GODOT_BIN=/path/to/Godot_v4.7.2-stable_linux.x86_64   # optional; enables import, verify, preview
examples/showcase-godot/build_showcase.sh
# when GODOT_BIN is set, the script already imports and may write preview/showcase.gif
"$GODOT_BIN" --headless --path examples/showcase-godot -- --verify
```

The integration test is `tests/test_showcase_godot.py` (the collision run is skipped
unless `GODOT_BIN` is set).

## Known gaps

`--headless` uses the dummy renderer, so preview frames need a real display or
`xvfb-run` plus a software GL driver (`LIBGL_ALWAYS_SOFTWARE=1`, `gl_compatibility`).
The player walk clip is three procedural blobs with a shifting contact shadow, not a
hand-authored character. The BMFont uses Pillow's bundled default face (no vendored
TTF). Blob tile 0 is an isolated grass cap; solid walls use stamped atlas index 47.

## Side-view platformer

A second project lives at `examples/showcase-platformer/`. It is a side-view
platformer: a 32×12 map from `map-blank` + `bake_level.py`, solid and one-way
colliders from `godot-tileset`, two 3-tile gaps that `jump-arc` must land on
the far platform (`end` and `out_of_bounds`, not `landed` alone) using the
same gravity (800), jump velocity (220) and speed (120) as the Godot scene, a
coin pickup SFX, three `tex-gen` parallax layers (also rendered by
`parallax-preview`), and a BMFont HUD. Player frames follow the same
tex-gen / pixelize / outline / canvas / shadow / atlas path as the top-down
showcase.

```bash
examples/showcase-platformer/build_showcase.sh
"$GODOT_BIN" --headless --path examples/showcase-platformer -- --verify
# success prints GST_PLATFORMER_OK
```

The integration test is `tests/test_showcase_platformer.py` (the scripted jump
is skipped unless `GODOT_BIN` is set). Preview shots are taken at 1.2s, 2.4s
and 3.6s of simulated time (movie maker records at 10 FPS; physics still
ticks at 60 Hz).
