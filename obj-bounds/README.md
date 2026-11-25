# obj-bounds

Report an OBJ's axis-aligned bounding box (min, max, size, centre, bounding-sphere radius) as JSON. Optional `--box` writes a 12-triangle AABB mesh, useful as a stand-in collider.

## Usage

```bash
python3 obj-bounds/obj_bounds.py hero.obj -o hero_bounds.json --box hero_aabb.obj
```

Run `python3 obj-bounds/obj_bounds.py --help` (or `gst obj-bounds --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Bounds are computed from `v` positions only (no transforms, no `o`/`g` subsets). Degenerate (zero-volume) meshes still report a radius of zero if every vertex is at one point. The AABB mesh has no UVs or materials.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
