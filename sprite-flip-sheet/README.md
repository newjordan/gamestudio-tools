# sprite-flip-sheet

Generate mirrored copies (horizontal, vertical, or both) of frames from a sheet plus atlas JSON, writing a new sheet and atlas. Original frames are kept; flipped copies are named with a suffix (`_h`, `_v`, `_hv`). Rotated frames are refused. The input is never overwritten.

## Usage

```bash
python3 sprite-flip-sheet/sprite_flip_sheet.py walk.png walk.json -o walk_flip.png --horizontal --pad 1
```

Run `python3 sprite-flip-sheet/sprite_flip_sheet.py --help` (or `gst sprite-flip-sheet --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). Complements sheet-pad, sprite-angles and atlas-pack.

## Source and licence

Original code. Rotated frames are refused. Trimmed `spriteSourceSize` x/y are copied as-is and are not mirrored, so a trimmed pivot may be wrong on the flipped copy.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
