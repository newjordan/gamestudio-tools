# frames-to-sheet

Turn an animated GIF/APNG/WebP or a folder of PNG frames into a sprite sheet + JSON (rects and per-frame durations), with uniform crop, nearest scaling, colour-key transparency and frame subsampling.

## Usage

```bash
python3 frames-to-sheet/frames_to_sheet.py clip.gif -o sheets/clip --key 00ff00 --columns 4 --scale 2
python3 frames-to-sheet/frames_to_sheet.py renders/turntable -o sheets/turntable --max-frames 16
```

Run `python3 frames-to-sheet/frames_to_sheet.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: video-to-sprite and animation generator workflows (post-step for H3 video clips; sprite-slice is the inverse).

## Source and licence

Original code; image decoding by Pillow. No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
