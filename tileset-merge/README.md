# tileset-merge

Combine two Tiled tileset files (JSON / TSJ / TSX) into one and optionally remap a map's GIDs so it points at the merged tileset. Image tilesets with the same tile size are packed into a new sheet (A's tiles, then B's). Collection tilesets concatenate their `tiles` arrays with remapped ids and animation `tileid`s.

## Usage

```bash
python3 tileset-merge/tileset_merge.py grass.tsj dirt.tsj -o terrain.tsj --map level.json --map-out level_merged.json
```

Run `python3 tileset-merge/tileset_merge.py --help` (or `gst tileset-merge --help`) for every option. Requires Python 3.10+. Pillow is required to pack image tilesets.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Mixed image/collection tilesets and different tile sizes are refused. Margin and spacing of the packed sheet come from tileset A. Wangsets are remapped when present; terrain and grid-orientation extras are not specially merged. The map matcher identifies tilesets by `source` basename or `name`.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
