# pixel-lint

Pixel-art hygiene linter: colour count, off-palette pixels, semi-transparent pixels, orphan pixels, near-duplicate colours, and accidental upscaling. Exit 1 on errors (--strict for warnings).

## Usage

```bash
python3 pixel-lint/pixel_lint.py art/sprites --max-colors 16 --palette palettes/game.hex --near 6
python3 pixel-lint/pixel_lint.py art/sprites --strict --json lint.json
```

Run `python3 pixel-lint/pixel_lint.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Pixelorama / LibreSprite workflows; complements asset-lint (files) and palette-extract (palettes).

## Source and licence

Original code (numpy).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
