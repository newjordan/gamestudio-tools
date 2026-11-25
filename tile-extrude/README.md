# tile-extrude

Rebuild a tileset with extruded edge pixels (and optional colour bleed into transparent pixels) so tiles stop showing seams or dark fringes when scaled, filtered or mipmapped. Prints the new margin/spacing to plug into Tiled, Godot or Unity.

## Usage

```bash
python3 tile-extrude/tile_extrude.py tiles.png -o tiles_x.png --tile 16x16 --extrude 2 --bleed 3
# prints {"tilewidth":16,...,"margin":2,"spacing":4,...}; use those values in the tileset import
```

Run `python3 tile-extrude/tile_extrude.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: tileset tooling around Tiled / LDtk / Godot TileMap (the classic 'tile bleeding' fix; cf. Tiled's tile-extruder community tool).

## Source and licence

Original code (numpy edge padding, neighbour-average colour dilation). The technique is long-standing common practice; no third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
