# ase-json-import

Aseprite sprite-sheet JSON (array or hash, with tags) to this kit's atlas JSON plus animation clips with per-frame durations, tag directions (forward, reverse, pingpong, pingpong_reverse) and `repeat` counts expanded with the same code as `ase-to-godot` (`lib/ase_tags.py`), and optional Phaser 3 anims JSON.

## Usage

```bash
python3 ase-json-import/ase_json_import.py hero.json -o hero --once hit --phaser hero_anims.json --atlas-key hero
```

A tag with `repeat` N plays N cycles and does not loop; other tags loop unless named in `--once`; `--ignore-direction` plays every tag forward and forever. Each clip records its `direction`. A two-frame ping-pong is `a, b` (it loops seamlessly), as in Aseprite.

Rotated frames are kept in the atlas JSON (`rotated: true`) so `atlas-to-godot` can unpack them. Slices are written to `<out>.slices.json` and `<out>.slices.tscn`: each slice is a `Node2D` with `metadata/bounds`, `metadata/pivot`, and, when a nine-slice `center` is present, `metadata/insets` (L,T,R,B) and `metadata/nine_slice`. `--sheet` (or `meta.image` next to the JSON) is used to crop a canvas-space PNG per slice (rotated frames are un-packed first) so a child `Sprite2D` can use `offset = -pivot`. Nine-slice slices also get a `StyleBoxTexture` `.tres` (`texture_margin_*` from the center insets). `--res` is the `res://` prefix for those resources.

Run `python3 ase-json-import/ase_json_import.py --help` (or `gst ase-json-import --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

LibreSprite (Aseprite-lineage sprite editor).

## Source and licence

Original code written from the public Aseprite sprite-sheet JSON layout (File > Export Sprite Sheet, JSON Data, Tags on). No Aseprite or LibreSprite code. Known gaps: frame-level user data and cels are not read; a tag's colour and user data are dropped; a slice with several keys uses the first key for the scene node (every key is still in the slices JSON); malformed exports give a typed one-line error, not a partial result.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
