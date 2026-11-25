# sprite-slice

Cut a sprite sheet into individual frames by fixed grid or by auto-detecting alpha islands, drop empty cells, write frames.json, and optionally an animated GIF preview.

## Usage

```bash
python3 sprite-slice/sprite_slice.py hero_walk.png --grid 32x32 -o frames/hero_walk --gif hero_walk.gif --fps 12
python3 sprite-slice/sprite_slice.py loose_icons.png --auto -o frames/icons
```

Run `python3 sprite-slice/sprite_slice.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: sprite sheet slicers (Aseprite/LibreSprite sheet import, Pixelorama).

## Source and licence

Original code (flood-fill island detection written from scratch). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
