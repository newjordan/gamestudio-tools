# sprite-pivot

Pivot/origin metadata for sprite frames: feet-centre, centre, alpha centroid or top-left, with optional per-animation alignment so frames do not jitter. Exports pixel pivot, Unity normalised pivot (y up) and Godot offset.

## Usage

```bash
python3 sprite-pivot/sprite_pivot.py walk_frames/ --mode feet --align-anim -o pivots.json
```

Run `python3 sprite-pivot/sprite_pivot.py --help` (or `gst sprite-pivot --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Pixelorama and LibreSprite (sprite authoring).

## Source and licence

Original code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
