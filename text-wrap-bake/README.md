# text-wrap-bake

Pre-wrap localisation strings to a pixel width with a real font and write the wrapped text (newlines in the cells) to a new CSV, so a simple in-game renderer can draw them without measuring. Uses loc-fit's wrapper. Limits can be a default width or a limits CSV with glob ids. The input file is never overwritten.

## Usage

```bash
python3 text-wrap-bake/text_wrap_bake.py strings.csv -o strings_wrapped.csv --font fonts/Main.ttf --size 18 --width 220
python3 text-wrap-bake/text_wrap_bake.py strings.csv -o out.csv --limits ui_limits.csv --langs fr,de
```

Run `python3 text-wrap-bake/text_wrap_bake.py --help` (or `gst text-wrap-bake --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Built on loc-fit; loc-check still validates placeholders and length ratios.

## Source and licence

Original code on Pillow's font metrics (see loc-fit). By default markup is stripped and placeholders are replaced with --placeholder before wrapping, and that visible text is what is written. --raw keeps tags and placeholders but may mis-measure markup. Complex scripts need an engine check.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
