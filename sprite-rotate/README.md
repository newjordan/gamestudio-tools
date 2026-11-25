# sprite-rotate

Rotate sprites by 90/180/270 degrees exactly, or by an arbitrary angle with nearest-neighbour sampling. 90-degree steps use a lossless transpose; other angles expand the canvas to fit unless `--keep-size` pads/crops back to the original size. When an atlas JSON is given (`--atlas` or a `.json` input), the packed sheet and every frame rect / sourceSize are rewritten (90/180/270 only). Folders or files in; writes `-o` (file or directory). The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 sprite-rotate/sprite_rotate.py hero.png -o hero_90.png --angle 90
python3 sprite-rotate/sprite_rotate.py hero.json -o hero90/ --angle 90
python3 sprite-rotate/sprite_rotate.py hero.png --atlas hero.json -o out.png --atlas-out out.json --angle 90
```

Run `python3 sprite-rotate/sprite_rotate.py --help` (or `gst sprite-rotate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Positive `--angle` is counter-clockwise (Pillow / mathematical convention). Arbitrary angles are nearest-neighbour and look jaggy; packed atlas rewrite is 90/180/270 only (unpack, rotate, and re-pack for other angles). Rotated packed frames (`rotated: true`) are refused. Animated GIFs are flattened to the first frame. `--keep-size` cannot be used when rewriting a packed atlas at 90 or 270 degrees.

## Tests

`python3 -m pytest -q tests/test_batch25.py tests/test_batch27.py`
