# bmfont-gen

Bake a bitmap font (BMFont text .fnt + PNG atlas) from any TTF/OTF, with chosen charset (or all characters from your localised strings), 1-bit pixel mode and padding.

## Usage

```bash
python3 bmfont-gen/bmfont_gen.py --font fonts/MyFont-Regular.ttf --size 16 --no-aa -o ui/font16
python3 bmfont-gen/bmfont_gen.py --font default --size 24 --charfile loc/all_strings.txt -o ui/font24
```

Run `python3 bmfont-gen/bmfont_gen.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: font/UI pipeline helpers (AngelCode BMFont, Hiero, msdf-atlas-gen).

## Source and licence

Original code; rendering by Pillow/FreeType. **You must have the right to embed the font** (use OFL/Apache/public-domain fonts for open-licence projects). `--font default` is Pillow's bundled font (Aileron, understood to be CC0; verify before shipping it).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
