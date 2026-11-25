# gif-optimize

Shrink review GIFs by flattening each frame onto a black background, quantising to a shared palette, optionally scaling, and writing with Pillow's GIF optimizer. Reports before/after bytes and frame count. The input is never overwritten.

## Usage

```bash
python3 gif-optimize/gif_optimize.py preview.gif -o preview_sm.gif --colors 32 --scale 0.5 --json report.json
```

Run `python3 gif-optimize/gif_optimize.py --help` (or `gst gif-optimize --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Complements spritesheet-gif, particle-preview and credits-roll.

## Source and licence

Original code. This is a review-size pass, not a substitute for gifsicle or a lossless archive. Frames are flattened onto black (alpha is not preserved). Dirty-rect / transparency disposal is not used; every frame is a full palettised image.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
