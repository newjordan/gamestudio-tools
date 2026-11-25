# sprite-recolor

Remap sprite colours from a palette or a from/to list, keeping alpha. `--map ff0000:00aaff,...` is an exact (or `--tolerance`) RGB replacement. `--from` / `--to` are index-matched palette files (`.hex` / GIMP `.gpl`, same reader as palette-swap). Folders or files in; writes `-o` (file or directory). Alpha is never modified. The input is never overwritten unless `--in-place`. For HSV shifts and named variants, use palette-swap.

## Usage

```bash
python3 sprite-recolor/sprite_recolor.py hero.png -o hero_blue.png --map ff0000:3366ff
python3 sprite-recolor/sprite_recolor.py frames/ -o out/ --from team.hex --to enemy.hex --tolerance 2
```

Run `python3 sprite-recolor/sprite_recolor.py --help` (or `gst sprite-recolor --help`) for every option. Requires Python 3.10+ (Pillow, numpy).

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

RGB only (no HSV). First matching colour wins when several source colours overlap under `--tolerance`. Palette files are index-matched, not nearest-colour. Animated GIFs are flattened to the first frame on load (Pillow convert).

## Tests

`python3 -m pytest -q tests/test_batch24.py`
