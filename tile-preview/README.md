# tile-preview

Render a Tiled JSON map to a PNG without an editor, for review screenshots and CI artefacts: tileset images (or flat colours), flip flags, layer selection, object overlays, grid, zoom and background.

## Usage

```bash
python3 tile-preview/tile_preview.py level1.json -o level1.png --scale 2 --grid --objects --bg '#202830'
python3 tile-preview/tile_preview.py cave.json -o cave.png --tileset tiles.png   # for maps with no tileset entry
```

Run `python3 tile-preview/tile_preview.py --help` (or `gst tile-preview --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Tiled (map editor).

## Source and licence

Original code from the public Tiled JSON format docs. Orthogonal, finite maps only; external .tsx / .tsj tilesets are resolved next to the map and animated tiles are drawn as their first frame.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
