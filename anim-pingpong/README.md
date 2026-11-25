# anim-pingpong

Expand anim-meta / ase-json-import clip JSON to a ping-pong frame list (and matching duration lists). Looping clips become `[f0..fn, fn-1..f1]` so a wrap back to f0 stays smooth; non-looping clips include the return to f0: `[f0..fn, fn-1..f0]`. Loop flags and fps stay put. `--clips` limits the work to named clips.

```
gst anim-pingpong clips.json -o clips_pp.json --pretty
gst anim-pingpong clips.json -o clips_pp.json --clips walk --clips idle
```

## Usage

```bash
python3 anim-pingpong/anim_pingpong.py clips.json -o clips_pp.json --pretty
python3 anim-pingpong/anim_pingpong.py clips.json -o clips_pp.json --clips walk --clips idle
```

Run `python3 anim-pingpong/anim_pingpong.py --help` (or `gst anim-pingpong --help`) for every option. Requires Python 3.10+.

## Known gaps

The expansion is applied once and is not detected or inverted; running the tool twice on the same file doubles the bounce. Clips with a single frame are left unchanged.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
