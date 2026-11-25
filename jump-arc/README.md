# jump-arc

Preview a 2D jump / gravity arc over a Tiled map (or a blank canvas) and report range and apex. Kinematic: x = x0 + vx t, y = y0 + vy t + 1/2 g t^2, with y down (Tiled space). `--jump-v` is upward launch speed and `--gravity` is a downward magnitude. The arc is sampled until it hits a solid cell (non-empty tile on `--solid-layer`, or any non-empty visible cell) or returns to the start height on a blank canvas. `--jumps N` repeats the jump each time the arc lands. Draws the polyline and apex on a tile-preview PNG. `--json` reports the sample polyline plus `range`, `apex`, `landed`, `end: [x, y]` and `out_of_bounds`. Leaving the map still sets `landed` to true, so a platform landing should be checked against `end` and `out_of_bounds`, not `landed` alone.

## Usage

```bash
python3 jump-arc/jump_arc.py maps/cave.json -o cave_jump.png --start 64,320 --jump-v 220 --speed 120 --gravity 800
python3 jump-arc/jump_arc.py -o arc.png --width 320 --height 180 --start 20,160 --json arc.json
```

Run `python3 jump-arc/jump_arc.py --help` (or `gst jump-arc --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). Complements map-reach (top-down walkability, no jump arcs).

## Source and licence

Original code. This is a kinematic preview (no coyote time, no variable jump, no one-way platforms, no air control).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
