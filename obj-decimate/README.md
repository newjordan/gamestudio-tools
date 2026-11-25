# obj-decimate

Reduce an OBJ's triangle count by grid vertex clustering (Rossignac and Borrel 1993, the same idea as glb-lod). `--ratio` is the target fraction of input triangles (default 0.5). N-gon faces are refused (run obj-triangulate first). mtllib, usemtl, group and smoothing lines are kept. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 obj-decimate/obj_decimate.py hero.obj -o hero_lod.obj --ratio 0.25
```

Run `python3 obj-decimate/obj_decimate.py --help` (or `gst obj-decimate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

A fast clustering simplifier, not a quality edge-collapse. N-gons are refused. UVs take the first vertex in a cluster (they are not averaged). Lines are remapped into the same clusters. skinned / animated meshes are out of scope (OBJ has no skins).

## Tests

`python3 -m pytest -q tests/test_batch25.py`
