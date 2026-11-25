# spritesheet-gif

Render an animation from a sprite sheet plus a clips JSON to a GIF, for review links and pull-request previews. Reads atlas-pack / ase-json-import JSON with anim-meta / ase clips (or Phaser anims, or a bounce/frames JSON). Trimmed frames are reconstructed onto their sourceSize canvas so the GIF does not jitter. --scale is nearest-neighbour; frames are flattened onto --bg (GIF has no real RGBA).

## Usage

```bash
python3 spritesheet-gif/spritesheet_gif.py atlas.json --clips clips.json -o review/ --scale 2
python3 spritesheet-gif/spritesheet_gif.py bounce_sheet.json -o bounce.gif --once
```

Run `python3 spritesheet-gif/spritesheet_gif.py --help` (or `gst spritesheet-gif --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). The reverse of gif-to-frames in spirit; clips come from anim-meta or ase-json-import.

## Source and licence

Original code on Pillow. GIF is palette-based and is flattened onto --bg, so it is a preview, not a lossless archive of the frames.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
