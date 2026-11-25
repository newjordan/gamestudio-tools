# palette-apply

Force sprites onto a palette (nearest colour, optional Floyd–Steinberg dither). The palette comes from a `.hex` / `.gpl` file, a JSON list, or is extracted from a reference image (via palette-swap's reader, or the unique opaque colours of a PNG). Alpha is kept (transparent pixels stay transparent). Folders or files in; writes `-o`. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 palette-apply/palette_apply.py hero.png -o hero_gb.png --palette pico8
python3 palette-apply/palette_apply.py frames/ -o out/ --palette colours.hex --dither
```

Run `python3 palette-apply/palette_apply.py --help` (or `gst palette-apply --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

This is a many-to-few quantise, not an exact colour remap (use palette-swap / sprite-recolor for that). Pillow's Floyd–Steinberg dither is used when `--dither` is set. Animated GIFs are flattened to the first frame. Built-in names are those accepted by pixelize (`pico8`, `gameboy`, …).

## Tests

`python3 -m pytest -q tests/test_batch27.py`
