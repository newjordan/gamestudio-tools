# obj-normals

Recompute vertex normals on an OBJ as flat (one normal per face) or smooth (averaged at each vertex, optionally split by an angle threshold and by smoothing groups). `s off` / `s 0` faces stay flat even in smooth mode. Materials and groups are kept.

## Usage

```bash
python3 obj-normals/obj_normals.py hero.obj -o hero_n.obj --mode smooth --angle 30
```

Run `python3 obj-normals/obj_normals.py --help` (or `gst obj-normals --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Angle splitting is per-corner against the face being written, not a global sharp-edge weld, so a smooth crease may still produce more unique normals than a DCC. Line (`l`) elements are copied unchanged. Existing `vn` records are replaced.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
