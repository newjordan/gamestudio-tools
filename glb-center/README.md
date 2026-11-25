# glb-center

Move a glTF/GLB scene so its world-space AABB sits on a chosen pivot (bbox centre by default, or feet / min corner / a point). The glTF-only counterpart of obj-recenter; the shift is applied to each scene root node, same as mesh-pivot-fix, and leaves vertex data and child animations untouched (warns when a skin or a root translation animation may override it). The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 glb-center/glb_center.py hero.glb -o hero_c.glb
python3 glb-center/glb_center.py hero.glb --report
```

Run `python3 glb-center/glb_center.py --help` (or `gst glb-center --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

World bounds come from POSITION accessor min/max (required by the spec); missing min/max is refused. Root-node translation is shifted, not the vertex buffer, so a skin or a root translation animation can override the result (a warning is printed). OBJ files are refused (use obj-recenter). Same behaviour as mesh-pivot-fix `--mode center` for glTF.

## Tests

`python3 -m pytest -q tests/test_batch25.py`
