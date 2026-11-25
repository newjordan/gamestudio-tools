# onion-skin

Animator review sheet: for each frame draw the previous frame(s) ghosted in red and the next frame(s) in blue under the frame itself, on one sheet (and optionally an animated GIF). Accepts a folder of PNGs, an animated GIF/APNG/WebP or a sprite sheet with --grid. The report flags duplicate frames and pops (large frame-to-frame changes).

## Usage

```bash
python3 onion-skin/onion_skin.py walk_frames/ -o onion.png --prev 2 --next 1 --loop --cols 4 --scale 3
python3 onion-skin/onion_skin.py walk_sheet.png --grid 32x32 -o onion.png --gif onion.gif
```

Run `python3 onion-skin/onion_skin.py --help` (or `gst onion-skin --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Frames can come from gif-to-frames or sprite-slice; anim-meta holds the timing.

## Source and licence

Original code on Pillow and numpy. Frames of different sizes are aligned bottom-centre. The change ratio is a rough pixel measure, not a motion analysis.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
