# sprite-canvas

Place sprites onto a fixed canvas size with an anchor (center, feet / bottom, top-left, ...). Larger images are cropped unless `--fit` (NEAREST scale-down) is set; `--upscale` also allows scaling up.

## Usage

```bash
python3 sprite-canvas/sprite_canvas.py frames -o padded --size 64x64 --anchor feet --bg #00000000
```

Run `python3 sprite-canvas/sprite_canvas.py --help` (or `gst sprite-canvas --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Scaling uses nearest-neighbour only (pixel art). There is no trim-to-content step (use sprite-trim first). Animated GIFs are flattened to the first frame that Pillow opens.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
