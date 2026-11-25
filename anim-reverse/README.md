# anim-reverse

Reverse anim-meta / ase-json-import clip JSON (frame order and matching duration lists). `--clips` limits the work to named clips; others are copied through. Loop flags and fps stay put; total `duration` is recomputed from per-frame durations when present. Writes a new JSON; the input is never overwritten.

## Usage

```bash
python3 anim-reverse/anim_reverse.py clips.json -o clips_rev.json --pretty
python3 anim-reverse/anim_reverse.py clips.json -o clips_rev.json --clips walk --clips jump
```

Run `python3 anim-reverse/anim_reverse.py --help` (or `gst anim-reverse --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements anim-meta, anim-retarget-fps and ase-json-import.

## Source and licence

Original code. Duration lists named `durations_ms`, `durations` or `times` are reversed with the frames.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
