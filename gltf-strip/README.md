# gltf-strip

Shrink a GLB/glTF by dropping unused meshes, materials, textures, images, accessors, bufferViews, cameras, skins and nodes, then packing the remaining views into a compact BIN. Optional: drop cameras, KHR_lights_punctual lights, extras, names, and animations whose targets are gone. Reports before/after sizes.

## Usage

```bash
python3 gltf-strip/gltf_strip.py props/crate.glb -o props/crate_lite.glb --drop-names --drop-extras
python3 gltf-strip/gltf_strip.py scene.glb -o scene_lite.glb --drop-cameras --drop-lights --json-report strip.json
```

Run `python3 gltf-strip/gltf_strip.py --help` (or `gst gltf-strip --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with gltf-inspect (budget check) and glb-lod (mesh simplification). Does not quantise vertices or transcode textures.

## Source and licence

Original code. Follows the glTF 2.0 specification (Khronos, public). Custom extensions may hold untracked references: check skinned or extension-heavy files in a viewer after stripping.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
