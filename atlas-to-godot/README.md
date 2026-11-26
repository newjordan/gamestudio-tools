# atlas-to-godot

Write a Godot 4 SpriteFrames `.tres` from an atlas JSON (atlas-pack / TexturePacker hash or array) plus its sheet. Frames become AtlasTexture sub-resources. Optional anim-meta / ase-json-import clips JSON groups them into named animations; otherwise every frame is one `default` animation, or `--per-frame` writes one animation per frame. The texture path is written as `res://...` (override with `--res`).

Rotated frames (TexturePacker / Aseprite: the packed rectangle is the sprite rotated 90° CW) are unpacked: the atlas region is cropped, rotated 90° CCW, and written as a sibling PNG (or under `--rotated-dir`), then referenced as an ExtResource. Godot 4 AtlasTexture has no rotation property, so this is the feasible path. The atlas sheet must be readable (`--sheet` or `meta.image`); without a sheet, rotated frames are still refused. `--rotated-res` sets the `res://` prefix for those PNGs. The input is never overwritten unless `--in-place`. Godot itself is not opened by this tool.

## Usage

```bash
python3 atlas-to-godot/atlas_to_godot.py atlas.json -o player.tres --clips clips.json --res res://art/player.png
python3 atlas-to-godot/atlas_to_godot.py atlas.json -o frames.tres --per-frame --fps 12
python3 atlas-to-godot/atlas_to_godot.py atlas.json -o hero.tres --sheet hero.png --rotated-dir art --rotated-res res://art
```

Run `python3 atlas-to-godot/atlas_to_godot.py --help` (or `gst atlas-to-godot --help`) for every option. Requires Python 3.10+ (Pillow when rotated frames must be unpacked).

Since 2.5.0 trimmed frames (atlas-pack's default) keep their original canvas: each AtlasTexture gets
`margin = Rect2(offset x, offset y, extra width, extra height)` from `spriteSourceSize` / `sourceSize`, so
animations no longer jitter or lose their pivot. Unpacked rotated frames are padded back to `sourceSize` too.

## Inspiration (catalogue entry)

None (new). Complements godot-tileset, godot-import-presets, atlas-pack and anim-meta.

## Source and licence

Original code from the documented Godot 4 text-resource layout. The `.tres` was loaded in official Godot 4.7.2.stable.official.ed1daf0bf (`GODOT_BIN` integration test): SpriteFrames `walk` with 3 frames, loop and fps intact, and an unpacked rotated frame whose texture size matches the upright sprite. Collision, filters and per-frame offsets are not emitted. Relative frame durations come from `durations_ms` when present, otherwise 1.0 at the clip fps. Clip frame names may be `walk_01.png` or `walk_01` (atlas-pack writes stems). Only the common 90° CW packed rotation is unpacked; other angles are not inferred.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
