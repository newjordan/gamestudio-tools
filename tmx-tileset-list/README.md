# tmx-tileset-list

List tilesets referenced by a Tiled JSON map (name, firstgid, image or source, tilecount, columns, and how many unique local ids are used on tile layers). External .tsx / .tsj tilesets are resolved next to the map. Optional JSON and CSV; `--fail-if-none` exits 1 when the map has no tilesets.

## Usage

```bash
python3 tmx-tileset-list/tmx_tileset_list.py level.json --json tilesets.json -o tilesets.csv
```

Run `python3 tmx-tileset-list/tmx_tileset_list.py --help` (or `gst tmx-tileset-list --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Object-tile GIDs are not counted in used_local_ids. A tileset without tilecount reports unused as null. Collection tilesets without an image are still listed.

## Tests

`python3 -m pytest -q tests/test_batch30.py`
