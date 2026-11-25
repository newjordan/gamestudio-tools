# sprite-scale

Nearest-neighbour scale of sprites by a uniform `--scale` factor or to an explicit `--size WxH`. When an atlas JSON is given (`--atlas` or a `.json` input), the packed sheet and every frame rect / sourceSize are rewritten (`--scale`, or `--size` as the new sheet size). Folders or files in; writes `-o` (file or directory). Alpha is kept. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 sprite-scale/sprite_scale.py hero.png -o hero_2x.png --scale 2
python3 sprite-scale/sprite_scale.py hero.json -o hero2x/ --scale 2
```

Run `python3 sprite-scale/sprite_scale.py --help` (or `gst sprite-scale --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Nearest-neighbour only (pixel art). Animated GIFs are flattened to the first frame. Rotated packed frames (`rotated: true`) are refused. `--size` on a packed atlas is the new sheet size (non-uniform scale is allowed). `--scale` rounds each loose-image dimension independently to at least 1 px.

## Tests

`python3 -m pytest -q tests/test_batch26.py tests/test_batch27.py`
