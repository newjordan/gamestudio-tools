# tmx-layer-export

Export each tile layer of a Tiled JSON map as a PNG (via tile-preview), plus a stacked composite. Layer files are named with a 2-digit index and a flattened path. Hidden layers are skipped unless `--include-hidden`. Encoded tile data is decoded and external `.tsx` / `.tsj` tilesets are resolved.

## Usage

```bash
python3 tmx-layer-export/tmx_layer_export.py maps/cave.json -o preview/cave --tileset tiles.png --bg 101018
python3 tmx-layer-export/tmx_layer_export.py maps/cave.json -o preview/cave --include-hidden --objects --scale 2
```

Run `python3 tmx-layer-export/tmx_layer_export.py --help` (or `gst tmx-layer-export --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). Complements tile-preview (one image for the whole map).

## Source and licence

Original code. Same limits as tile-preview: finite orthogonal maps only.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
