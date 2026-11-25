# terrain-noise

Seeded fBm / ridged gradient-noise heightmaps (tileable or island) exported as 8-bit PNG, 16-bit PNG, raw .r16 (Unity/Unreal), and an RGBA biome splatmap.

## Usage

```bash
python3 terrain-noise/terrain_noise.py -o terrain/island01 --size 513 --island --ridged --seed 42
# -> island01_8.png  island01_16.png  island01.r16  island01_splat.png (R sand, G grass, B rock, A snow)
```

Run `python3 terrain-noise/terrain_noise.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: FastNoiseLite (MIT), Terrain3D for Godot, World Machine / Gaea workflows.

## Source and licence

Original vectorised Perlin-style gradient noise in numpy (Ken Perlin's improved-noise fade curve 6t^5-15t^4+10t^3 is a published formula). No FastNoiseLite code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
