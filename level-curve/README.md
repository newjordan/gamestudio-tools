# level-curve

Generate and sanity-check XP, stat or cost curves (linear, polynomial, exponential, or geometric interpolation between anchors) with cumulative totals, ratios, target totals, hours per level, spike warnings, CSV/JSON and an SVG chart.

## Usage

```bash
python3 level-curve/level_curve.py --kind custom --levels 50 --anchors '1:100,10:1500,50:400000' --nice --per-hour 20000 --csv xp.csv --svg xp.svg --log
```

Run `python3 level-curve/level_curve.py --help` (or `gst level-curve --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with game-data-lint and data-diff.

## Source and licence

Original code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
