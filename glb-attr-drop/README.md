# glb-attr-drop

Drop named vertex attributes from a static GLB (NORMAL, TEXCOORD_0, COLOR_0, TANGENT, …). POSITION cannot be dropped. The file is rebuilt from the remaining float attributes, indices, and images. Animated, skinned, morphed or sparse-accessor files are refused. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 glb-attr-drop/glb_attr_drop.py prop.glb -o prop_slim.glb --drop NORMAL,TEXCOORD_0
```

Run `python3 glb-attr-drop/glb_attr_drop.py --help` (or `gst glb-attr-drop --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Binary .glb only, triangle lists, float32 attributes (same limits as glb-lod). Other accessors (joints, weights) are dropped because the file is rebuilt from mesh primitives and images only. Names must match the glTF attribute keys exactly.

## Tests

`python3 -m pytest -q tests/test_batch28.py`
