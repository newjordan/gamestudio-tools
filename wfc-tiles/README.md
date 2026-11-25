# wfc-tiles

Learn tile-adjacency rules from a small example map (CSV ids, or a PNG where each pixel is a tile) and generate new maps of any size with Wave Function Collapse; outputs CSV, PNG, or Tiled JSON.

## Usage

```bash
python3 wfc-tiles/wfc_tiles.py examples/room.csv -o level01.json --size 40x24 --seed 3
python3 wfc-tiles/wfc_tiles.py examples/overworld.png -o world.png --size 96x64 --scale 8 --wrap
```

Run `python3 wfc-tiles/wfc_tiles.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: mxgmn/WaveFunctionCollapse (MIT), DeBroglie, Tessera.

## Source and licence

Clean-room implementation of the 'simple tiled' WFC idea (min-entropy observe + propagate). Concept credit: Maxim Gumin, mxgmn/WaveFunctionCollapse (MIT). No code copied.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
