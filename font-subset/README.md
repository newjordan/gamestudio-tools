# font-subset

Shrink a TTF/OTF to the characters your game uses (found in text, CSV, yarn and ink files, plus extras), keeping kerning and ligatures; optional WOFF output and hinting removal; reports size saved and characters the font lacks.

## Usage

```bash
python3 font-subset/font_subset.py fonts/Main.ttf strings.csv dialogue.yarn --ascii -o fonts/Main-subset.ttf
python3 font-subset/font_subset.py fonts/Main.ttf strings.csv --flavor woff
```

Run `python3 font-subset/font_subset.py --help` (or `gst font-subset --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with font-check and bmfont-gen.

## Source and licence

Original wrapper around fontTools (MIT licence, optional dependency). Check that each font's licence allows subsetting and embedding (SIL OFL fonts do; some commercial fonts do not). WOFF2 needs the brotli package.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
