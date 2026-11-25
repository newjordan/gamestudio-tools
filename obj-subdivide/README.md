# obj-subdivide

Midpoint-subdivide every triangle in an OBJ (`--times`, default 1). Each pass replaces a triangle with four; midpoints on shared edges are reused so the mesh stays watertight. UVs and normals are interpolated when both endpoints have them. N-gon faces are refused (run obj-triangulate first). mtllib, usemtl, groups are kept. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 obj-subdivide/obj_subdivide.py prop.obj -o prop_sub.obj
python3 obj-subdivide/obj_subdivide.py prop.obj -o prop_sub2.obj --times 2
```

Run `python3 obj-subdivide/obj_subdivide.py --help` (or `gst obj-subdivide --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

N-gons are refused rather than auto-triangulated. Subdivision is uniform midpoint only (no Loop / Catmull-Clark limit surface, no crease weights). Lines (`l`) are left untouched. Vertex colours on `v` lines, if present, are not interpolated.

## Tests

`python3 -m pytest -q tests/test_batch26.py`
