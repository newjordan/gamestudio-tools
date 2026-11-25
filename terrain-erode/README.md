# terrain-erode

Erode a heightmap PNG: thermal (talus slumping) and grid-based hydraulic (rain, flow, sediment, deposition) erosion, both mass conserving and deterministic, with a flow map output and optional tiling.

## Usage

```bash
python3 terrain-erode/terrain_erode.py height.png -o eroded.png --flow flow.png --hydraulic 80 --thermal 20 --wrap
```

Run `python3 terrain-erode/terrain_erode.py --help` (or `gst terrain-erode --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Terrain3D and FastNoiseLite (terrain tooling).

## Source and licence

Original code (numpy). A simple grid model, not a particle-based erosion simulation; it softens and carves gullies rather than matching a specific commercial eroder.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
