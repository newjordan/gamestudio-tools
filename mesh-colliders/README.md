# mesh-colliders

Derive collision primitives from a GLB: world-space AABB, PCA-oriented box, bounding sphere and a Y-capsule, per node and overall, with Godot shape sizes. Node transforms are applied.

## Usage

```bash
python3 mesh-colliders/mesh_colliders.py props/crate.glb -o props/crate_colliders.json --per-node
```

Run `python3 mesh-colliders/mesh_colliders.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Godot / glTF-Transform asset pipeline entries.

## Source and licence

Original code. Sphere is Ritter's approximate bounding sphere (a few percent over minimal); the oriented box is PCA-based, not a minimal-volume box.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
