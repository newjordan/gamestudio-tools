# mesh-pivot-fix

Move a model's pivot to its bounding-box centre, bottom centre (feet), min corner or a chosen point, and report the bounds before and after. GLB/glTF: shifts the scene's root nodes by the offset (exact for any hierarchy, vertex data untouched, BIN chunk preserved byte for byte). OBJ: translates vertex positions.

## Usage

```bash
python3 mesh-pivot-fix/mesh_pivot_fix.py props/crate.glb -o props/crate_fixed.glb --mode bottom
python3 mesh-pivot-fix/mesh_pivot_fix.py props/rock.obj --mode center
python3 mesh-pivot-fix/mesh_pivot_fix.py props/crate.glb --report
```

Run `python3 mesh-pivot-fix/mesh_pivot_fix.py --help` (or `gst mesh-pivot-fix --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with gltf-inspect (bounds) and glb-lod.

## Source and licence

Original code. Follows the glTF 2.0 specification (Khronos, public) for node transforms and accessor min/max. Warns when skins or root-node translation animations may override the shift.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
