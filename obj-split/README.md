# obj-split

Split an OBJ into one file per `g` / `o` group (or only groups, or only objects with `--by g|o|both`), remapping `v` / `vt` / `vn` indices so each file is self-contained. Material (`mtllib`, `usemtl`), smoothing and comment lines that belong to a group travel with it; the file prelude is copied onto every output. Writes under `--outdir`. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 obj-split/obj_split.py props.obj -o parts/
python3 obj-split/obj_split.py props.obj -o parts/ --by g --json parts.json
```

Run `python3 obj-split/obj_split.py --help` (or `gst obj-split --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Splits on `g` / `o` lines only (not on `usemtl`). Groups with no faces or lines are dropped. A later group that re-uses an earlier name gets a `_2` suffix. Skin weights, curves and other non-triangle OBJ features are not handled (same limit as obj-weld / obj-merge).

## Tests

`python3 -m pytest -q tests/test_batch24.py`
