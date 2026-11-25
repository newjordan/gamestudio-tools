# ldtk-to-tiled

Convert an LDtk project (or a single level) to Tiled JSON maps, one file per level. Tile and auto-layers become tile layers (LDtk flip bits map to Tiled H/V flip flags). Entity layers become object groups with field values as Tiled properties. Tilesets come from the project's `defs.tilesets` with packed firstgids. External level files are loaded with `--levels-dir`, same as ldtk-to-csv.

## Usage

```bash
python3 ldtk-to-tiled/ldtk_to_tiled.py project.ldtk -o maps/ --pretty
python3 ldtk-to-tiled/ldtk_to_tiled.py project.ldtk -o maps/ --level Intro
```

Run `python3 ldtk-to-tiled/ldtk_to_tiled.py --help` (or `gst ldtk-to-tiled --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

IntGrid layers are exported as raw integer grids (not a tileset). Composite / enum / entity-ref field values are JSON-stringified. Rotated LDtk tiles (if any) are not mapped to Tiled's diagonal flip flag.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
