# glb-weld

Weld nearby vertices in a static GLB (the glTF counterpart of obj-weld). Vertices whose positions quantise to the same `--epsilon` cell are merged; optional `--also-uv` / `--also-normal` add TEXCOORD_0 / NORMAL to the key so seams stay split. Degenerate triangles are dropped. Animated, skinned, morphed or sparse-accessor files are refused. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 glb-weld/glb_weld.py prop.glb -o prop_weld.glb --epsilon 1e-5
```

Run `python3 glb-weld/glb_weld.py --help` (or `gst glb-weld --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Binary .glb only, triangle lists, float32 attributes (same limits as glb-lod). Other accessors (animation, inverse bind matrices) are dropped because the file is refused if they would matter. Images are copied. The first vertex in a cell is kept (positions are not averaged).

## Tests

`python3 -m pytest -q tests/test_batch26.py`
