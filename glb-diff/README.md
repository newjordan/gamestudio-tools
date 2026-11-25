# glb-diff

Review aid for model changes: compare two GLB/glTF files on triangles, vertices, bytes, meshes, materials, textures, animations, bounds and extensions. `--max-tri-increase` and `--max-size-increase` give a CI exit code.

## Usage

```bash
python3 glb-diff/glb_diff.py old.glb new.glb
python3 glb-diff/glb_diff.py old.glb new.glb --max-tri-increase 10 --max-size-increase 25 --json diff.json
```

Run `python3 glb-diff/glb_diff.py --help` (or `gst glb-diff --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

glTF-Transform (inspect/diff style tooling).

## Source and licence

Original code built on this kit's gltf-inspect; no code from glTF-Transform.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
