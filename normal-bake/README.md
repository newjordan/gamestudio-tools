# normal-bake

Derive height, normal (OpenGL or DirectX), ambient-occlusion and roughness maps from one albedo texture on CPU, with tileable edge handling.

## Usage

```bash
python3 normal-bake/normal_bake.py stone_albedo.png -o mats/stone --strength 6
python3 normal-bake/normal_bake.py wall.png -o mats/wall --directx --no-tile   # Unreal green channel
```

Run `python3 normal-bake/normal_bake.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: DeepBump (GPL-3.0), Materialize, NormalMap-Online. This is the classic image-processing version, not the ML model.

## Source and licence

Original code (central-difference gradients, blurred-difference AO). **No code from DeepBump** (GPL) was used or consulted; only the general idea of single-image map generation.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
