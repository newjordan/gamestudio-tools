# material-audit

Walk a folder (or list) of GLB / glTF files and report unique materials, texture slots (baseColor, metal-rough, normal, occlusion, emissive, plus common KHR extras), and missing image URIs. Embedded images (bufferView or data URI) count as present; an external URI must exist next to the file. Text, JSON and CSV; `--fail-on-missing` for CI.

## Usage

```bash
python3 material-audit/material_audit.py assets/models/ --json audit.json --fail-on-missing
python3 material-audit/material_audit.py hero.glb prop.glb --csv mats.csv
```

Run `python3 material-audit/material_audit.py --help` (or `gst material-audit --help`) for every option. Requires Python 3.10+ (uses gltf-inspect to load GLB/glTF).

## Inspiration (catalogue entry)

None (new). Complements gltf-inspect (per-file stats) and gltf-strip (dropping unused resources).

## Source and licence

Original code, from the Khronos glTF 2.0 material layout. Custom extensions outside the listed KHR texture slots are named but not walked for hidden URIs.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
