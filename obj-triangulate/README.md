# obj-triangulate

Turn n-gon faces in a Wavefront OBJ into triangles with ear-clipping, so concave faces stay inside the original polygon. Vertex, UV and normal index tokens are kept as written. `mtllib`, `usemtl`, group (`g` / `o`), smoothing (`s`) and comment lines are copied through in order. Self-intersecting or degenerate faces that cannot be ear-clipped fall back to a triangle fan and are counted in the JSON report as `fan_fallback`.

```
gst obj-triangulate mesh.obj -o mesh_tri.obj
```

## Usage

```bash
python3 obj-triangulate/obj_triangulate.py mesh.obj -o mesh_tri.obj
```

Run `python3 obj-triangulate/obj_triangulate.py --help` (or `gst obj-triangulate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Self-intersecting and zero-area faces fall back to a triangle fan (reported as `fan_fallback`). `l` / `p` lines are copied, not tessellated. Faces with holes are not supported. Ear-clipping projects each face to 2D by dropping the dominant axis of its Newell normal; a face that is folded in 3D may be classified poorly.

## Tests

`python3 -m pytest -q tests/test_batch19.py` (convex / metadata) and `tests/test_batch21.py` (concave n-gon).
