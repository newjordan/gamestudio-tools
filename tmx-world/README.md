# tmx-world

Build a Tiled `.world` index from a folder of finite maps (or an explicit list). Placement is taken from each map's `chunk_x` / `chunk_y` properties when `--from-props` (the default after map-chunk), from a trailing `_X_Y` filename when `--from-filename`, or laid out in a left-to-right grid with `--layout grid --columns N`. Pixel sizes come from each map's tile size. The world file is never an in-place overwrite of a source map unless `--in-place`.

## Usage

```bash
python3 tmx-world/tmx_world.py chunks/ -o world.world
python3 tmx-world/tmx_world.py maps/ -o world.world --layout grid --columns 4
```

Run `python3 tmx-world/tmx_world.py --help` (or `gst tmx-world --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

JSON / TMX maps; `.world` paths are relative to the output file. `--from-filename` treats the last two integers in the stem as tile coordinates (the same convention as map-chunk's `chunk_X_Y.json`). Maps that cannot be placed are a hard error unless `--layout grid` is used. Map contents are not rewritten.

## Tests

`python3 -m pytest -q tests/test_batch26.py`
