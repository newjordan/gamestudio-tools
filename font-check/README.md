# font-check

Find characters your game text needs that a font does not contain (they would show as empty boxes), for TTF/OTF/TTC fonts and BMFont `.fnt` files, with code points and counts.

## Usage

```bash
python3 font-check/font_check.py strings.csv dialogue.yarn --font fonts/Main.ttf --font fonts/pixel.fnt
```

Run `python3 font-check/font_check.py --help` (or `gst font-check --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with bmfont-gen and loc-check.

## Source and licence

Original code. Uses fontTools' cmap when it is installed (recommended); otherwise it compares rendering against the missing-glyph box. Pillow's bundled default font lacks e-acute and CJK, so bmfont-gen with `--font default` would bake empty boxes for them; use a real TTF.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
