# sprite-sheet-optimize

Shrink an existing sprite sheet or atlas: trim transparent borders, store identical frames once (every name still resolves, with an alias_of field), and repack with MaxRects over many sheet widths, keeping the smallest area. Pixels are never resampled and every frame reconstructs exactly from the new sheet plus its offsets.

## Usage

```bash
python3 sprite-sheet-optimize/sprite_sheet_optimize.py atlas.json --image atlas.png -o atlas_small
python3 sprite-sheet-optimize/sprite_sheet_optimize.py atlas.json -o atlas_small --pot --max-width 1024 --padding 2
```

Run `python3 sprite-sheet-optimize/sprite_sheet_optimize.py --help` (or `gst sprite-sheet-optimize --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Reads atlas-pack output and writes the same layout; atlas-validate checks the result and atlas-convert exports it to other engines.

## Source and licence

Original code. Uses the MaxRects packer from atlas-pack (custom, after J. Jylanki, A Thousand Ways to Pack the Bin, 2010). JSON layouts follow the common hash and array atlas formats. Rotated frames are refused, not guessed at.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
