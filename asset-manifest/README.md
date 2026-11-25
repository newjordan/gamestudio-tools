# asset-manifest

Deterministic content-hash manifest of an asset folder (sha256, bytes, image size, WAV duration), with diff (added/removed/changed/renamed + patch size) and verify; CI-friendly exit codes.

## Usage

```bash
python3 asset-manifest/asset_manifest.py build game/assets -o manifests/build_042.json
python3 asset-manifest/asset_manifest.py diff manifests/build_041.json manifests/build_042.json --fail
python3 asset-manifest/asset_manifest.py verify manifests/build_042.json game/assets
```

Run `python3 asset-manifest/asset_manifest.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: asset pipeline / patching tools (CI asset checks; complements asset-lint).

## Source and licence

Original code (hashlib, wave, Pillow). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
