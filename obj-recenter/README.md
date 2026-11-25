# obj-recenter

Move an OBJ so its bounding-box centre, bottom (feet) or min corner sits at the origin. `--up y|z` picks the up axis for `--mode bottom`. Vertex colours and all non-`v` lines (mtllib, usemtl, groups, smoothing, comments, faces) are kept. The input is never overwritten. Sibling of mesh-pivot-fix, OBJ only.

## Usage

```bash
python3 obj-recenter/obj_recenter.py prop.obj -o prop_c.obj --mode center
python3 obj-recenter/obj_recenter.py prop.obj -o prop_feet.obj --mode bottom --up z --json report.json
```

`--mode centre` is accepted as an alias of `center`. `--report` prints bounds and writes nothing. Run `python3 obj-recenter/obj_recenter.py --help` (or `gst obj-recenter --help`) for every option. Requires Python 3.10+ with numpy.

## Inspiration (catalogue entry)

None (new). Complements mesh-pivot-fix and obj-weld.

## Source and licence

Original CLI; the vertex shift is the same routine as mesh-pivot-fix (optional vertex colours kept). glTF/GLB files should go through mesh-pivot-fix.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
