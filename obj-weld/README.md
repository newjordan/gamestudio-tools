# obj-weld

Weld vertices that sit within `--epsilon` of each other in an OBJ. Faces are remapped and degenerate faces dropped. OBJ relative (negative) vertex indices are honoured. Writes a new file; refuses to overwrite the input. Reports vertex counts before and after.

## Usage

```bash
python3 obj-weld/obj_weld.py mesh.obj -o mesh_welded.obj --epsilon 1e-5 --json weld.json
```

Run `python3 obj-weld/obj_weld.py --help` (or `gst obj-weld --help`) for every option. Requires Python 3.10+ with numpy.

## Inspiration (catalogue entry)

None (new). Complements glb-lod (grid clustering of a GLB) and obj-to-glb.

## Source and licence

Original code. `mtllib`, `usemtl`, group (`g`/`o`), smoothing (`s`) and comment lines are preserved in order relative to the faces they prefix. GLB welding is not implemented in this version (convert to OBJ, weld, then obj-to-glb).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
