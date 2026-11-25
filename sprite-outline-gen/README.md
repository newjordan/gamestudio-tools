# sprite-outline-gen

Add a 1px or N-px outline to sprites, animation frames or a grid sheet: outer (around the silhouette), inner (eaten from the edge) or both, 4- or 8-connected. Several frames share the same padding so animations stay aligned. Distinct from sprite-fx, which only grows an outer outline and also bakes shadows and flashes.

## Usage

```bash
python3 sprite-outline-gen/sprite_outline_gen.py sprites/ -o outlined/ --width 2 --color '#101018'
python3 sprite-outline-gen/sprite_outline_gen.py sheet.png -o sheet_ol.png --grid 32x32 --mode inner
```

Run `python3 sprite-outline-gen/sprite_outline_gen.py --help` (or `gst sprite-outline-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with sprite-fx (shadows, flashes) and sprite-shadow (drop/contact shadows).

## Source and licence

Original code on Pillow and numpy. Reuses the mask dilation from sprite-fx. Semi-transparent edges follow --threshold (default 0: any alpha > 0 is solid). --keep-size may clip an outer outline.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
