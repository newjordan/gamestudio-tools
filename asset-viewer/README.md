# asset-viewer

Bake a single self-contained HTML file to eyeball an atlas (frame outlines, hover names), a Tiled-style map (coloured or with a tileset), or a folder of frames (contact grid + play). No server, no network.

## Usage

```bash
python3 asset-viewer/asset_viewer.py atlas atlas.png atlas.json -o atlas.html
python3 asset-viewer/asset_viewer.py map level.json --tileset tiles.png --tile 16x16 -o level.html
python3 asset-viewer/asset_viewer.py frames frames/hero_walk -o walk.html --fps 12
```

Run `python3 asset-viewer/asset_viewer.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Tiled / LDtk viewers, atlas preview tools.

## Source and licence

Original code (plain JS + canvas, embedded as base64). **Known gap: JS syntax-checked with `node --check` and data round-tripped in tests, but not interactively tested in a browser in this build.**

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
