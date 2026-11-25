# palette-extract

Extract a palette from one or many images and save .hex (Lospec), .gpl (GIMP/Aseprite/Krita) and a swatch PNG; exact when few colours, median-cut otherwise; sort by luminance, hue or frequency.

## Usage

```bash
python3 palette-extract/palette_extract.py art/hero.png art/bg.png -o palettes/game -n 16 --sort hue
python3 pixelize/pixelize.py concept.png -o px.png -p palettes/game.hex
```

Run `python3 palette-extract/palette_extract.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Pixelorama / Lospec palette workflows; feeds pixelize and palette-swap.

## Source and licence

Original code; median cut by Pillow (MIT-CMU). Median cut runs on unique colours (frequency is not weighted).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
