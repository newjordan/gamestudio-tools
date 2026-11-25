# anim-retarget-fps

Rewrite animation clip frame durations to a new fps grid while keeping each clip's total time. Reads anim-meta / ase-json-import clips JSON. Each duration is snapped to a whole number of ticks of 1000/fps milliseconds (at least one tick); any remainder is added to the last frame. The clip's `fps` field is updated. Writes a new JSON; refuses to overwrite the input.

## Usage

```bash
python3 anim-retarget-fps/anim_retarget_fps.py clips.json -o clips_12.json --fps 12
python3 anim-retarget-fps/anim_retarget_fps.py walk.json -o walk_30.json --fps 30 --json-report retarget.json
```

Run `python3 anim-retarget-fps/anim_retarget_fps.py --help` (or `gst anim-retarget-fps --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements frame-timing-check (which flags off-grid timings) and anim-meta (which groups frames).

## Source and licence

Original code. The new total can differ from the original by at most one tick (1000/fps ms) because of rounding.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
