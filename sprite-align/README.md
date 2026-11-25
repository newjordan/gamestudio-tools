# sprite-align

Place sprites onto one shared canvas so a common anchor (feet, center, centroid, or a compass point) of each sprite's opaque content lines up. Loose images are rewritten. When an atlas JSON is given, sourceSize and spriteSourceSize are rewritten and packed sheet pixels stay put.

## Usage

```bash
python3 sprite-align/sprite_align.py frames/ -o aligned/ --anchor feet
python3 sprite-align/sprite_align.py sheet.json -o sheet_aligned.json --anchor feet
```

Run `python3 sprite-align/sprite_align.py --help` (or `gst sprite-align --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Packed frames with rotated: true are refused. Atlas rewrite does not change the sheet image or packed rects. Centroid here is the mid-point of the opaque bounding box, not a mass centroid. Animated GIFs are flattened to the first frame by Pillow.

## Tests

`python3 -m pytest -q tests/test_batch30.py`
