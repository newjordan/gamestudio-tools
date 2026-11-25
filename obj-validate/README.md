# obj-validate

Check an OBJ for out-of-range face indices, degenerate faces (duplicate corners or zero area), unreferenced vertices, and vn/vt index errors. Prints a report and exits 1 when errors are present (warnings alone exit 0 unless `--strict`). Optional `--json`. This is a checker, not a rewriter.

## Usage

```bash
python3 obj-validate/obj_validate.py prop.obj
python3 obj-validate/obj_validate.py prop.obj --strict --json report.json
```

Run `python3 obj-validate/obj_validate.py --help` (or `gst obj-validate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not check watertightness, self-intersection, or material files. Degeneracy is a fan-from-first-vertex area test, so a non-planar n-gon can pass if any triangle in the fan has area. Unreferenced vertices are warnings, not errors.

## Tests

`python3 -m pytest -q tests/test_batch28.py`
