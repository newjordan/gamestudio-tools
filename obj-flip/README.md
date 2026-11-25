# obj-flip

Mirror an OBJ across an axis (`--axis x|y|z`). Vertex positions and normals are negated on that axis; triangle winding is reversed so the mesh does not turn inside-out. mtllib, usemtl, groups and smoothing lines are kept. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 obj-flip/obj_flip.py hero.obj -o hero_m.obj --axis x
```

Run `python3 obj-flip/obj_flip.py --help` (or `gst obj-flip --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

UVs are not mirrored (mirror v over x does not flip U). Two flips on the same axis are identity for positions, and winding is reversed twice (also identity). For combined scale/flip/rotate, use obj-transform (which does not reverse winding).

## Tests

`python3 -m pytest -q tests/test_batch27.py`
