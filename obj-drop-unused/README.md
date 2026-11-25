# obj-drop-unused

Drop unreferenced v, vt and vn records from a Wavefront OBJ and remap face (and line) corners. Material, group and smoothing lines are kept.

## Usage

```bash
python3 obj-drop-unused/obj_drop_unused.py mesh.obj -o mesh_tight.obj --json report.json
```

Run `python3 obj-drop-unused/obj_drop_unused.py --help` (or `gst obj-drop-unused --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only v / vt / vn tables are compacted. Unused mtllib / usemtl names are not touched. Degenerate faces are not removed (see obj-weld / obj-validate).

## Tests

`python3 -m pytest -q tests/test_batch30.py`
