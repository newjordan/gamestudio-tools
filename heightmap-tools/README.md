# heightmap-tools

Edits for greyscale heightmaps (8 or 16 bit in, 16 bit out): gaussian blur (tileable option), terrace, clamp-and-stretch, normalize, invert, bilinear resize (for 2^n+1 sizes) and a slope map in degrees.

## Usage

```bash
python3 heightmap-tools/heightmap_tools.py terrace height.png -o stepped.png --steps 6 --sharp 6
python3 heightmap-tools/heightmap_tools.py resize height.png -o h513.png --size 513
python3 heightmap-tools/heightmap_tools.py slope height.png -o slope.png --height-scale 60
```

Run `python3 heightmap-tools/heightmap_tools.py --help` (or `gst heightmap-tools --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Terrain3D and FastNoiseLite (terrain tooling).

## Source and licence

Original code (numpy, Pillow).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
