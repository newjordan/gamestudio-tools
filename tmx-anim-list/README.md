# tmx-anim-list

List tile animations in a Tiled tileset or map (tiles[].animation = [{tileid, duration}, ...]). External .tsx / .tsj tilesets are resolved next to the file. Optional JSON and CSV reports; --fail-if-none exits 1 when nothing is animated.

## Usage

```bash
python3 tmx-anim-list/tmx_anim_list.py tiles.json --json anims.json -o anims.csv
```

Run `python3 tmx-anim-list/tmx_anim_list.py --help` (or `gst tmx-anim-list --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not play or rewrite animations (see tile-anim-gif). Collection tilesets without an image are still scanned. Object-tile animations are not listed.

## Tests

`python3 -m pytest -q tests/test_batch29.py`
