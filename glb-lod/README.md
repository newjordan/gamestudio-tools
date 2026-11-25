# glb-lod

Make LOD copies of static .glb meshes via grid vertex clustering (binary search to hit a triangle ratio), keeping UVs, normals and embedded textures. Refuses skinned, animated, morph or sparse files.

## Usage

```bash
python3 glb-lod/glb_lod.py props/rock.glb -o props/lod --ratios 0.5,0.25,0.1
# -> rock_lod1.glb rock_lod2.glb rock_lod3.glb; check with gltf-inspect
```

Run `python3 glb-lod/glb_lod.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: glTF-Transform (MIT; has proper simplify via meshoptimizer), mesh-optimisation tools. This is the dependency-free fast option for distant LODs and collision proxies; for hero meshes use a real edge-collapse simplifier.

## Source and licence

Original code. Vertex clustering is a textbook technique (Rossignac and Borrel, 1993). No code from glTF-Transform or meshoptimizer.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
