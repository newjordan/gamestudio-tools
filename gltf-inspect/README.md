# gltf-inspect

Zero-dependency glTF/GLB inspector with budgets: vertex/triangle counts, materials, embedded texture sizes, animations, skins, bounds, and warnings (no normals or UVs, non-indexed geometry, >65k verts, texture or tri budgets).

## Usage

```bash
python3 gltf-inspect/gltf_inspect.py props/*.glb --max-tris 15000 --max-tex 2048
python3 gltf-inspect/gltf_inspect.py hero.glb --json > hero_stats.json
# CI: add --fail-on-warn
```

Run `python3 gltf-inspect/gltf_inspect.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: glTF-Transform `inspect` (MIT), gltf-validator.

## Source and licence

Original code written from the Khronos glTF 2.0 specification (spec is openly published). Concept credit: donmccurdy/glTF-Transform (MIT). No code copied.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
