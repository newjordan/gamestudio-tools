# GST platformer showcase (Godot 4.7)

A side-view platformer whose textures, tileset, Tiled map, coin SFX, parallax
layers, BMFont HUD and player SpriteFrames are all produced by kit generators.
Required jumps are checked with `jump-arc` against the same gravity, jump
velocity and horizontal speed the Godot scene uses (`800`, `220`, `120`).

Official Godot 4.7.2 on the box is used only to import, run a scripted jump
across the first gap, and (when a display or xvfb is available) record a short
software-GL preview GIF. The Godot binary is not in the kit tarball.

## Layout

A 32×12, 16 px-tile map: solid floors at tile-row 10 with two 3-tile gaps
(48 px, inside the ~66 px same-height jump range). A one-way platform sits
above the second floor (`one_way` collider from `godot-tileset`). A coin on
the second floor plays a generated pickup SFX. Three `tex-gen` layers, cropped
to 640×180, scroll behind the stage (`parallax-preview` also writes a layer GIF).

## Rebuild

```bash
export GODOT_BIN=/path/to/Godot_v4.7.2-stable_linux.x86_64   # optional
./build_showcase.sh
```

The script wipes `art/`, `sfx/`, `font/` and `preview/`, then regenerates them.
Authored files (`project.godot`, `scenes/`, `scripts/`, `bake_level.py`,
`import_rules.json`, this README, the build script) are left alone.

Jump validation fails the build if a gap's `jump-arc` report has
`out_of_bounds` or an `end` point that is not on the far platform. (`landed`
alone is not enough: leaving the map is also counted as landed.)

## Verify

```bash
"$GODOT_BIN" --headless --path . -- --verify
```

The player walks at 120 px/s, jumps at each takeoff, and after 90 physics
frames must be on the floor of the second platform. Success prints
`GST_PLATFORMER_OK`.

## Licence

Same licence as the rest of the kit (none applied yet; MIT has been suggested).
