# sprite-unpad

Crop padding off each sprite (the inverse of sprite-pad, not a trim-to-opaque-bbox — that is sprite-trim). `--pad N` or `--pad LEFT,TOP,RIGHT,BOTTOM`. When an atlas JSON is given, each frame's sourceSize and spriteSourceSize shrink so trim offsets stay correct; packed frame rects are left alone. The crop is refused if it would clip packed content or shrink a canvas below 1x1. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 sprite-unpad/sprite_unpad.py hero_pad.png -o hero.png --pad 2
python3 sprite-unpad/sprite_unpad.py padded/ -o raw/ --pad 2,4,2,4 --atlas padded.json
```

Run `python3 sprite-unpad/sprite_unpad.py --help` (or `gst sprite-unpad --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

This crops a fixed margin, not the opaque bounding box (use sprite-trim). Packed frame rectangles are not moved. Animated GIFs are flattened to the first frame. A sprite-pad / sprite-unpad pair with the same `--pad` is identity for loose images.

## Tests

`python3 -m pytest -q tests/test_batch28.py`
