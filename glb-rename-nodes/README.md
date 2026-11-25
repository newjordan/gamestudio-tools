# glb-rename-nodes

Batch-rename glTF/GLB nodes, meshes and materials (and optionally animations, scenes, skins, cameras, images, accessors) with a regex and replacement. `--dry-run` prints a report without writing. Skins and animation channels address nodes by index, so those indices stay intact. The input is never overwritten.

## Usage

```bash
python3 glb-rename-nodes/glb_rename_nodes.py hero.glb --pattern Hero --repl Boss --dry-run --json report.json
python3 glb-rename-nodes/glb_rename_nodes.py hero.glb -o boss.glb --pattern Hero --repl Boss
```

Run `python3 glb-rename-nodes/glb_rename_nodes.py --help` (or `gst glb-rename-nodes --help`) for every option. Requires Python 3.10+ (uses mesh-pivot-fix for GLB I/O).

## Inspiration (catalogue entry)

None (new). Complements gltf-inspect, gltf-strip and material-audit.

## Source and licence

Original code. Custom extras and extension objects are not walked for names. Empty names get a `target_index` placeholder before the regex.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
