# map-reach

Can the player get there? Flood-fill a Tiled JSON map (top-down, finite) from a start tile over walkable cells; report cut-off walkable areas and which objects (doors, keys, exits) are unreachable. Solid cells come from a collision layer and/or tile ids; text, JSON and PNG overlay output; CI exit codes via --require and --fail-on-islands.

## Usage

```bash
python3 map-reach/map_reach.py level.json --solid-layer collision --require exit,key --png reach.png
python3 map-reach/map_reach.py level.json --solid-ids 2 --start 5,3 --diagonal --adjacent --fail-on-islands --min-island 4
```

Run `python3 map-reach/map_reach.py --help` (or `gst map-reach --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Works on dungeon-gen, wfc-tiles and tilemap-convert output as well as maps from Tiled.

## Source and licence

Original code. Reads Tiled's documented JSON map format. 4-way or 8-way breadth-first search; platformer jump reachability is NOT modelled. Infinite maps and encoded tile data are refused.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
