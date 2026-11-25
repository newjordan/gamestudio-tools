# glb-quantize

Snap float POSITION, NORMAL and TEXCOORD accessors in a static GLB to a grid (`--digits` decimal places, or `--step`). Normals are renormalised afterwards. The first vertex in a cell is not merged (that is glb-weld). Animated, skinned, morphed or sparse-accessor files are refused. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 glb-quantize/glb_quantize.py prop.glb -o prop_q.glb --digits 3
python3 glb-quantize/glb_quantize.py prop.glb -o prop_q.glb --step 0.001 --uv-digits 4
```

Run `python3 glb-quantize/glb_quantize.py --help` (or `gst glb-quantize --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Binary .glb only, triangle lists, float32 attributes (same limits as glb-lod). Other accessors (joints, weights, colors) are dropped because the file is rebuilt from mesh primitives and images only. This reduces precision; it does not compress the buffer (use a glTF packer for that).

## Tests

`python3 -m pytest -q tests/test_batch27.py`
