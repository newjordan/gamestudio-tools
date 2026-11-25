# build-report

One Markdown build report for an assets folder, combining asset-lint, asset-manifest and gltf-inspect: pass/fail, size by type, lint findings, model stats and changes since a previous manifest. Single CI step.

## Usage

```bash
python3 build-report/build_report.py game/assets -o reports/build_042.md --prev-manifest manifests/build_041.json --save-manifest manifests/build_042.json --max-tris 15000
```

Run `python3 build-report/build_report.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: CI asset-check workflows (AssetRegulationManager-style gates).

## Source and licence

Original code; imports the sibling tools in this repo by relative path, so keep the folder layout.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
