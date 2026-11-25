# tileset-gen

Generate a 47-tile blob (8-neighbour) autotile sheet from two terrain fills (colour or tiling PNG), with a JSON that has a 256-entry raw-mask lookup so game code can index tiles straight from neighbour bits.

## Usage

```bash
python3 tileset-gen/tileset_gen.py -o grass_dirt --tile 16 --border 4 --inner grass.png --outer '#8a6a3f' --edge-color '#2d5a24'
```

Run `python3 tileset-gen/tileset_gen.py --help` (or `gst tileset-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Tiled (terrain/autotile workflows).

## Source and licence

Original code. Hard-edged pixel-art tiles only (no rounded corners); the neighbour-bit convention (N=1 NE=2 E=4 SE=8 S=16 SW=32 W=64 NW=128) differs from autotile-gen's 4-bit one, so use this tool's lookup.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
