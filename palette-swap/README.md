# palette-swap

Make recolour variants (enemy tiers, team colours, day/night) by exact/tolerant colour map, index-matched palette files, HSV shift, or a JSON file of named variants. Alpha preserved.

## Usage

```bash
python3 palette-swap/palette_swap.py slime.png -o out --map "3cc83c:3c78dc"
python3 palette-swap/palette_swap.py slime.png -o out --variants variants.json   # {"blue":{"3cc83c":"3c78dc"},"ghost":{"hue":180,"sat":0.5}}
python3 palette-swap/palette_swap.py hero.png -o out --from base.hex --to winter.hex
```

Run `python3 palette-swap/palette_swap.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: pixel-art workflow tools (Pixelorama, Aseprite palette workflows, Lospec palettes).

## Source and licence

Original code; HSV conversion by Pillow (MIT-CMU). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
