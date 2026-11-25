# sprite-shadow

Add a drop shadow (offset, blur, colour, opacity) or a soft contact ellipse under the feet to sprites and animation frames. The canvas grows so nothing is cut off, with the same padding for every frame so animations keep one size; --keep-size crops back to the input size.

## Usage

```bash
python3 sprite-shadow/sprite_shadow.py walk_frames/ -o walk_shadow/ --mode contact --opacity 0.6
python3 sprite-shadow/sprite_shadow.py orb.png -o orb_shadow.png --dx 3 --dy 3 --blur 1.5
```

Run `python3 sprite-shadow/sprite_shadow.py --help` (or `gst sprite-shadow --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with sprite-fx and frames-to-sheet.

## Source and licence

Original code on Pillow (HPND) and numpy. Pixel-art shadows are a style choice: use --blur 0 for hard-edged shadows.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
