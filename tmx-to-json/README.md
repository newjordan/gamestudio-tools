# tmx-to-json

Convert Tiled TMX (XML) maps to Tiled JSON: layers (csv, base64, zlib, gzip), object groups (points, ellipses, polygons, polylines, properties), tilesets (embedded or external reference), group and image layers and map properties.

## Usage

```bash
python3 tmx-to-json/tmx_to_json.py level1.tmx level2.tmx -o json/
```

Run `python3 tmx-to-json/tmx_to_json.py --help` (or `gst tmx-to-json --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Tiled (map editor).

## Source and licence

Original code from the public TMX and Tiled JSON format docs. zstd-compressed layers are decoded (native decoder if importable, else the kit's pure-Python one); external `.tsx` tilesets are kept as a `source` reference, not expanded.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
