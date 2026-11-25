# asset-lint

Rule-based pre-commit/CI linter for asset folders: naming regex, max texture size, power-of-two, alpha required/forbidden, file-size budget, WAV sample rate/channels, forbidden file types. Exits 1 on errors.

## Usage

```bash
python3 asset-lint/asset_lint.py game/assets
python3 asset-lint/asset_lint.py --write-default-rules asset_rules.json   # then edit
python3 asset-lint/asset_lint.py game/assets -r asset_rules.json --strict --json lint.json
```

Run `python3 asset-lint/asset_lint.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: CyberAgent AssetRegulationManager (MIT, Unity-only). This is an engine-agnostic CLI.

## Source and licence

Original code. Concept credit: CyberAgentGameEntertainment/AssetRegulationManager (MIT). No code copied.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
