# terrain-mesh

Heightmap PNG (8 or 16-bit) to GLB terrain with smooth normals and UVs, optional subsampling and an NxN chunk split whose edges meet without cracks.

## Usage

```bash
python3 terrain-mesh/terrain_mesh.py terrain/island01_16.png -o terrain/island.glb --scale 512,60,512 --step 2 --chunks 4
```

Run `python3 terrain-mesh/terrain_mesh.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Terrain3D / terrain tooling; takes terrain-noise output; check with gltf-inspect and uv-check.

## Source and licence

Original code (numpy gradient normals, grid triangulation).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
