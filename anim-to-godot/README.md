# anim-to-godot

Write a Godot 4 SpriteFrames `.tres` from an anim-meta clips JSON plus a folder of frame images. Use atlas-to-godot when the frames already live on a packed sheet.

## Usage

```bash
python3 anim-to-godot/anim_to_godot.py clips.json --frames ./frames -o hero_frames.tres --res res://frames/ --json report.json
```

Run `python3 anim-to-godot/anim_to_godot.py --help` (or `gst anim-to-godot --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not pack frames into an atlas (use atlas-pack, then atlas-to-godot). Frame names must match files in the folder (with or without `.png`). Godot import settings for the PNGs are not written.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
