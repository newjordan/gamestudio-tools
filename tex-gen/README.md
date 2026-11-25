# tex-gen

Procedural tileable prototype textures (bricks, planks, checker, cells/stone, noise) with colour options, plus matching height and normal maps; every pattern tiles seamlessly and is seed-deterministic.

## Usage

```bash
python3 tex-gen/tex_gen.py bricks -o bricks.png --size 256 --height --normal --seed 5
python3 tex-gen/tex_gen.py planks -o wood.png --color-a '#c49a6c' --color-b '#8a5a2b'
```

Run `python3 tex-gen/tex_gen.py --help` (or `gst tex-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Material Maker (procedural materials).

## Source and licence

Original code; uses this kit's terrain-noise for periodic noise. Intended for greybox surfaces, not final art.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
