# loc-fit

Will the translation fit its UI box? Measure every string of a localisation CSV with a real font and size against per-string pixel limits (limits CSV with glob ids, or a default), wrap overflowing strings (word or character wrap) and judge them against a line limit. Placeholders and markup are neutralised before measuring. Text, CSV and JSON output; exit 1 on overflow.

## Usage

```bash
python3 loc-fit/loc_fit.py strings.csv --font fonts/Main.ttf --size 18 --limits ui_limits.csv --out-csv fit.csv
python3 loc-fit/loc_fit.py strings.csv --limit-default 220 --max-lines 2 --only-failing
```

Run `python3 loc-fit/loc_fit.py --help` (or `gst loc-fit --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Complements loc-check (length ratios) and pseudoloc (stress text); bmfont-gen and font-check cover the font side.

## Source and licence

Original code on Pillow's font metrics (HPND). Measures with basic layout: kerning/shaping for complex scripts (Arabic, Indic) is not modelled, so re-check those in the engine. Check each font's licence before shipping it.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
