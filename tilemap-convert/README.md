# tilemap-convert

Convert tile maps between Tiled JSON, CSV and ASCII, and print per-layer tile statistics. Tiled flip flags are masked, and a warning is printed when any were lost.

## Usage

```bash
python3 tilemap-convert/tilemap_convert.py to-csv level.json -o csv/level
python3 tilemap-convert/tilemap_convert.py from-ascii level.txt -o level.json --legend ".:1,#:2" --tile 16x16
python3 tilemap-convert/tilemap_convert.py stats level.json
```

Run `python3 tilemap-convert/tilemap_convert.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Tiled (GPL editor, open JSON map format), LDtk.

## Source and licence

Original code. Reads/writes the documented Tiled JSON map format (data format only; no Tiled code used).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
