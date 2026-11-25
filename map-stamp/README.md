# map-stamp

Stamp a prefab Tiled JSON (tile layers and/or objects) onto a target map at a tile or pixel position. Prefab tilesets are merged into the target (same rules as map-merge). Tile cells overwrite by default; `--empty-only` writes only onto empty cells. Objects are copied with new ids. Writes a new map; refuses to overwrite the target. Encoded tile data is decoded.

## Usage

```bash
python3 map-stamp/map_stamp.py maps/overworld.json --prefab prefabs/chest_room.json -o maps/overworld_stamped.json --at 12,8
python3 map-stamp/map_stamp.py maps/base.json --prefab decor.json -o out.json --at-px 192,64 --empty-only --prefix deco_
```

Run `python3 map-stamp/map_stamp.py --help` (or `gst map-stamp --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-merge (several whole maps into one).

## Source and licence

Original code. Orthogonal maps, same tile size. Cells that would land outside the target are skipped.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
