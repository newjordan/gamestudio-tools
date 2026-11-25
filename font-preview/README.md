# font-preview

Render a font review sheet (pangram, digits, and optional extra lines or unique characters from a localisation CSV) at several pixel sizes, and list missing glyphs. Missing glyphs are detected from the font's cmap via fontTools (preferred). Pillow's bundled default font has no cmap, so a `.notdef` tofu cannot be told from a real glyph there; pass a real TTF/OTF. Characters that are missing are also boxed in red on the sheet.

## Usage

```bash
python3 font-preview/font_preview.py fonts/Game.ttf -o preview.png --sizes 16,24,32 --csv loc/en-ja.csv --json missing.json
python3 font-preview/font_preview.py default -o default.png --sizes 16 --no-pangram --text "Hello"
```

Run `python3 font-preview/font_preview.py --help` (or `gst font-preview --help`) for every option. Requires Python 3.10+ with Pillow. fontTools is required for reliable missing-glyph detection on real TTF/OTF files.

## Inspiration (catalogue entry)

None (new). Complements font-check (metrics and coverage reports) and font-subset (building a smaller TTF).

## Source and licence

Original code. Uses Pillow for rasterisation and fontTools `cmap` tables when available. There is no complex-script shaping (HarfBuzz / ICU); ligatures and combining marks need an engine check.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
