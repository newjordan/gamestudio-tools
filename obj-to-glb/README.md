# obj-to-glb

Convert Wavefront .obj + .mtl to a single .glb: triangulation, per-material primitives, Kd colours and embedded map_Kd textures, generated flat normals, V-flip, scale and Z-up fix.

## Usage

```bash
python3 obj-to-glb/obj_to_glb.py models/*.obj -o glb --scale 0.01
python3 obj-to-glb/obj_to_glb.py scan.obj -o glb --up-axis z
```

Run `python3 obj-to-glb/obj_to_glb.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: glTF-Transform / Blender import-export pipelines; closes the 'OBJ in, GLB out' gap without Blender.

## Source and licence

Original code from the OBJ/MTL conventions and the Khronos glTF 2.0 spec. No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
