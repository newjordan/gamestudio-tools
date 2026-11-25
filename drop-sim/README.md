# drop-sim

Check loot tables against intent: exact per-kill probability and expected quantity per item (nested tables supported), a seeded Monte Carlo run with 95% intervals, pity-timer simulation, kills needed for 50% and 90%, and CI assertions.

## Usage

```bash
python3 drop-sim/drop_sim.py loot.json --trials 100000 --expect goblin:dagger:0.03:0.05 --json report.json
```

Run `python3 drop-sim/drop_sim.py --help` (or `gst drop-sim --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with game-data-lint.

## Source and licence

Original code. Exact figures ignore pity (only the simulation models it); weights are relative and rolls are independent.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
