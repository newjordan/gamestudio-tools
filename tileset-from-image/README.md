# tileset-from-image

Slice a tileset PNG and audit it against the Tiled maps that use it: empty tiles, exact duplicates, per-tile use counts and never-used tiles, with an annotated PNG (unused tinted red, duplicates outlined blue, empties hatched) and CI exit codes.

## Usage

```bash
python3 tileset-from-image/tileset_from_image.py art/tiles.png maps/*.json --tile 16 --png audit.png --json audit.json
python3 tileset-from-image/tileset_from_image.py art/tiles.png maps/*.json --tile 16 --fail-on-unused
```

Run `python3 tileset-from-image/tileset_from_image.py --help` (or `gst tileset-from-image --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Exact duplicates only; tile-dedupe handles flipped and rotated duplicates and rewrites maps.

## Source and licence

Original code. Reads Tiled's documented JSON map format (finite and infinite maps, groups, flip flags). Reuses the tile slicing of tile-dedupe. Maps with encoded (base64/CSV string) tile data are refused; export as plain JSON arrays.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
