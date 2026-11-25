# obj-transform

Scale, flip, and/or rotate a Wavefront OBJ by 90/180/270 degrees around an axis (right-hand rule). Vertex and vertex-normal lines are rewritten (normals are inverse-scaled and renormalized). Faces, UVs, `mtllib`, `usemtl`, groups and smoothing lines are copied through.

## Usage

```bash
python3 obj-transform/obj_transform.py mesh.obj -o out.obj --scale 2
python3 obj-transform/obj_transform.py mesh.obj -o out.obj --flip x --rotate 90 --axis y
```

Run `python3 obj-transform/obj_transform.py --help` (or `gst obj-transform --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

UV coordinates are not flipped or rotated (optional --uv-flip is not implemented). `vp` and free-form geometry are copied unchanged.  Non-90-degree rotations are not supported.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
