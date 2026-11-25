# autotile-gen

Build a 16-tile (4-bit N/E/S/W) autotile sheet from one 3x3 template image, plus a JSON map of bitmask to tile index, and a helper to compute the mask of a cell in your own grid. Diagonal-aware 47-tile blob sets are not generated (they need an inner-corner art slot).

## Usage

```bash
python3 autotile-gen/autotile_gen.py grass_template.png --tile 16 -o tiles/grass_auto
# tile index = N(1)+E(2)+S(4)+W(8) of the neighbours that are the same terrain
```

Run `python3 autotile-gen/autotile_gen.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Tiled terrain / LDtk auto-layers, Godot TileMap terrains (this makes the art sheet they consume).

## Source and licence

Original code. The 4-bit bitmask autotile idea is a standard, widely documented technique.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
