# sprite-reframe

Place each sprite onto a new source canvas of --size WxH with a sprite-canvas anchor. Loose images are rewritten. When an atlas JSON is given, sourceSize and spriteSourceSize are rewritten and packed sheet pixels stay put; a size that would clip packed content is refused.

## Usage

```bash
python3 sprite-reframe/sprite_reframe.py frames/ -o reframed/ --size 32x32 --anchor feet
python3 sprite-reframe/sprite_reframe.py sheet.json -o sheet_reframed.json --size 32x32 --anchor center
```

Run `python3 sprite-reframe/sprite_reframe.py --help` (or `gst sprite-reframe --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Packed frames with rotated: true are refused. Atlas rewrite does not change the sheet image or packed rects (use sprite-canvas / sprite-pad to edit pixels). --fit scale is not offered here (that is sprite-canvas).

## Tests

`python3 -m pytest -q tests/test_batch29.py`
