# anim-hold

Pad an anim-meta clip to a target duration by extending the last frame's duration, or by repeating the last frame. `--add-frames N` appends the last frame N times first.

## Usage

```bash
python3 anim-hold/anim_hold.py clips.json -o held.json --clip idle --to-duration 1.5 --mode extend
```

Run `python3 anim-hold/anim_hold.py --help` (or `gst anim-hold --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Clips without `durations_ms` and without a `duration` field are padded by repeating frames at `fps` (default 12). Nested / multi-track clips are not a format this kit uses. `--mode extend` on a frames-only clip with no duration field falls back to `--mode repeat`.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
