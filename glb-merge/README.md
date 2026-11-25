# glb-merge

Merge several glTF / GLB files into one scene. Buffers are concatenated and bufferView, accessor, mesh, material, texture, image, sampler, node, skin and animation indices are remapped. Each input's default-scene roots become children of a wrapper node named after the file stem.

## Usage

```bash
python3 glb-merge/glb_merge.py hero.glb sword.glb -o hero_with_sword.glb
```

Run `python3 glb-merge/glb_merge.py --help` (or `gst glb-merge --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

External (non-data-URI) buffer or image files are refused. Morph-target weights on nodes pass through; extensions are copied but not remapped. `.gltf` sidecars with loose `.bin` files are not packed first — convert to GLB before merging.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
