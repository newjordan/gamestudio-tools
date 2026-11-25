# obj-uv-unwrap

First-pass UVs for an OBJ that has none: box projection (six axis islands, uniform texel density) or planar projection, keeping positions, normals, groups and materials; refuses to overwrite existing UVs without --force.

## Usage

```bash
python3 obj-uv-unwrap/obj_uv_unwrap.py blockout.obj -o blockout_uv.obj --mode box --padding 0.02
```

Run `python3 obj-uv-unwrap/obj_uv_unwrap.py --help` (or `gst obj-uv-unwrap --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

xatlas (real UV atlas generation; this tool is a much simpler projection).

## Source and licence

Original code. Projection, not an unwrapper: concave meshes can overlap in UV space (check with uv-check), and organic models need a real unwrap in Blender or xatlas.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
