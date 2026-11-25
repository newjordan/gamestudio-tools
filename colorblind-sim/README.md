# colorblind-sim

Preview images under protanopia, deuteranopia, tritanopia and achromatopsia, and check that a palette (team colours, rarity tiers) stays distinguishable using CIE76 delta-E under each simulation.

## Usage

```bash
python3 colorblind-sim/colorblind_sim.py sim screenshot.png -o cb/
python3 colorblind-sim/colorblind_sim.py palette '#e03030,#30b030,#3060e0' --min-delta 10
```

Run `python3 colorblind-sim/colorblind_sim.py --help` (or `gst colorblind-sim --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code using the published Machado, Oliveira and Fernandes (2009) matrices in linear RGB. Approximates dichromacy for design review; it is not a medical tool and real vision varies.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
