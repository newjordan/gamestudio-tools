# asset-rename

Safe batch renamer for asset files: snake, kebab or lower case, replacements, regexes, prefix and suffix; dry run by default, collision checks before touching anything, undo log, and exact-name reference fixing in text files.

## Usage

```bash
python3 asset-rename/asset_rename.py run assets/ --case snake --ext-lower                 # dry run
python3 asset-rename/asset_rename.py run assets/ --case snake --ext-lower --apply --fix-refs game/
python3 asset-rename/asset_rename.py undo rename_undo.json
```

Run `python3 asset-rename/asset_rename.py --help` (or `gst asset-rename --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with asset-lint's naming rules.

## Source and licence

Original code. Only file names change, not folders. Reference fixing rewrites whole file names only, in common text formats; binary and unusual formats are not scanned, so grep before trusting it.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
