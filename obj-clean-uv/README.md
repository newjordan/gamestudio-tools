# obj-clean-uv

Clean Wavefront OBJ texture coordinates: optional clamp to the 0–1 square, weld of duplicate UVs within an epsilon, and drop of unreferenced vt records, remapping face corners. Positions, normals, and material / group lines are kept.

## Usage

```bash
python3 obj-clean-uv/obj_clean_uv.py mesh.obj -o mesh_uv.obj --clamp --weld 0.0001
```

Run `python3 obj-clean-uv/obj_clean_uv.py --help` (or `gst obj-clean-uv --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only the first two vt components are considered. Weld buckets are a rounded grid (not a true spatial join), so UVs just under one epsilon apart can fall into different cells. Faces without UVs are left alone.

## Tests

`python3 -m pytest -q tests/test_batch29.py`
