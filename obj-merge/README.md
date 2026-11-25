# obj-merge

Merge several OBJ files into one, remapping `v` / `vt` / `vn` indices and keeping groups. Each file is prefixed with `g <stem>` / `o <stem>`, and existing group / object names are prefixed with that stem so they stay unique.

## Usage

```bash
python3 obj-merge/obj_merge.py body.obj lid.obj -o pot.obj
```

Run `python3 obj-merge/obj_merge.py --help` (or `gst obj-merge --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

MTL files are not merged or rewritten (`mtllib` / `usemtl` lines are copied as-is, so material file paths stay relative to each source). Relative (negative) indices are resolved per file when loading. Only OBJ is accepted (not GLB).

## Tests

`python3 -m pytest -q tests/test_batch23.py`
