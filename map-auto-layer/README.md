# map-auto-layer

Build a decoration tile layer from a JSON rule table over a Tiled ground layer. Each rule can match a centre GID and a 4- or 8-neighbour pattern (solid vs empty, or exact GIDs); the first matching rule wins.

## Usage

```bash
python3 map-auto-layer/map_auto_layer.py map.json --rules edges.json -o map_deco.json --name edges
```

Run `python3 map-auto-layer/map_auto_layer.py --help` (or `gst map-auto-layer --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Infinite maps are refused (run tmx-infinite-to-finite first). Rules do not inspect Wang / terrain data — only GIDs and neighbours. Flip flags on the source cell are ignored when matching (the unmasked GID is used); placed GIDs are written as given.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
