# patch-pack

Ship only what changed: build a patch zip from an asset-manifest of the old build and the new folder (add, change, remove, rename), then check-and-apply it with sha256 verification before and after. Dry-run supported, zip path traversal rejected.

## Usage

```bash
python3 asset-manifest/asset_manifest.py build old_build/ -o old.json
python3 patch-pack/patch_pack.py make old.json new_build/ -o update.zip
python3 patch-pack/patch_pack.py apply update.zip game_dir/ --dry-run   # then --out new_dir/ or in place
```

Run `python3 patch-pack/patch_pack.py --help` (or `gst patch-pack --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Builds on asset-manifest.

## Source and licence

Original code. Not a binary-delta patcher: changed files ship whole (the zip is compressed), renames are free.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
