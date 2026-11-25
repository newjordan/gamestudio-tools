# room-graph

Extract door / portal connections from Tiled object layers into mermaid and Graphviz DOT, with a reachability check. Rooms are objects of type `room`, or each input map is one room (the file stem) if none are found. Edges come from door / portal / exit / entrance / warp objects with a `target` / `to` / `dest` / `room` property, or from a matching `pair` property. `--start` (default: a spawn object, else the first room) is used for BFS. `--fail-on-unreachable` exits 1 when any room cannot be reached.

## Usage

```bash
python3 room-graph/room_graph.py maps/*.json --mermaid rooms.mmd --dot rooms.dot --json rooms.json --fail-on-unreachable
python3 room-graph/room_graph.py campaign/hub.json --start overworld
```

Run `python3 room-graph/room_graph.py --help` (or `gst room-graph --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-reach (walkability inside one map) and dialogue-graph (Yarn/ink nodes).

## Source and licence

Original code. Connections are taken from object properties, not from overlapping door tiles or engine-specific portal components.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
