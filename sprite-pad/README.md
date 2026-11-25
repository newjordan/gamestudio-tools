# sprite-pad

Add transparent padding around each sprite (not between packed sheet frames — that is sheet-pad). `--pad N` or `--pad LEFT,TOP,RIGHT,BOTTOM`. When an atlas JSON is given, each frame's sourceSize and spriteSourceSize are rewritten so trim offsets stay correct; packed frame rects are left alone. Folders or files in; writes `-o`. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 sprite-pad/sprite_pad.py hero.png -o hero_pad.png --pad 2
python3 sprite-pad/sprite_pad.py frames/ -o padded/ --pad 2,4,2,4 --atlas frames.json
```

Run `python3 sprite-pad/sprite_pad.py --help` (or `gst sprite-pad --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

This pads each sprite's own canvas. To add space between already-packed frames, use sheet-pad. Animated GIFs are flattened to the first frame. Packed frame rectangles are not moved (the sheet is not repacked).

## Tests

`python3 -m pytest -q tests/test_batch27.py`
