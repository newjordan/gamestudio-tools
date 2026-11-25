# glb-uv-transform

Scale, offset or flip UV (`TEXCOORD_*`) accessors in a GLB / glTF. The transform is `uv * scale + offset`, then optional `--flip-u` / `--flip-v` as `1 - u` or `1 - v`. Rewritten accessors are tightly packed float32 with updated min/max.

## Usage

```bash
python3 glb-uv-transform/glb_uv_transform.py prop.glb -o prop_uv.glb --scale 2,2 --offset 0.1,0 --flip-v
```

Run `python3 glb-uv-transform/glb_uv_transform.py --help` (or `gst glb-uv-transform --help`) for every option. Requires Python 3.10+ and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Sparse accessors and external (non-data-URI) buffers are refused. Only TEXCOORD accessors referenced by mesh primitives are rewritten; animation samplers that reuse those accessors would see the transformed values. Integer normalized UVs are converted to float32.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
