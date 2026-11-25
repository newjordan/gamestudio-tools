# image-diff

Visual regression for art: compare two images or folders, report changed-pixel percentage, max/mean difference and change bounding box, write red heatmaps, and fail past a threshold.

## Usage

```bash
python3 image-diff/image_diff.py art_v1/ art_v2/ -o diffs/ --tol 4 --max-changed 5
python3 image-diff/image_diff.py before.png after.png
```

Run `python3 image-diff/image_diff.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: asset pipeline / CI checks; use after palette-swap, pixelize or any batch conversion.

## Source and licence

Original code (numpy). Hidden RGB under fully transparent pixels is ignored.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
