# frame-timing-check

Validate animation clip timings against a target fps grid: off-grid frame durations, mixed durations in a clip that claims a constant fps, stored fps that does not match the durations, too-short or too-long frames or clips, empty clips and 1-frame loops. Reads anim-meta / ase-json-import clips, Aseprite sheet JSON, Phaser 3 anims, and gif-to-frames lists.

## Usage

```bash
python3 frame-timing-check/frame_timing_check.py clips.json --fps 12 --strict
python3 frame-timing-check/frame_timing_check.py hero_ase.json --allow-variable --min-ms 16 --report timing.json
```

Run `python3 frame-timing-check/frame_timing_check.py --help` (or `gst frame-timing-check --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Checks clips produced by anim-meta, ase-json-import and gif-to-frames.

## Source and licence

Original code. The fps grid is 1000/fps milliseconds; times are rounded to whole milliseconds, so 12 fps (83.333 ms) needs a tolerance of at least 0.5 ms (the default is 1). Aseprite hold frames will flag as variable unless you pass --allow-variable.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
