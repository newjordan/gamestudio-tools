# map-diff

Review diff of two Tiled JSON maps: settings and tileset changes, layers added, removed or reordered, changed-cell counts with bounding box and top tile swaps per layer, objects added, removed, moved or edited (matched by id), and property changes. Text, Markdown and JSON output with a CI exit code.

## Usage

```bash
python3 map-diff/map_diff.py maps/old/level1.json maps/new/level1.json
python3 map-diff/map_diff.py old.json new.json --md review.md --fail-on-diff
```

Run `python3 map-diff/map_diff.py --help` (or `gst map-diff --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). The map counterpart of data-diff and glb-diff.

## Source and licence

Encoded (base64 zlib/gzip or csv) tile data is decoded first; zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap). Original code. Reads Tiled's documented JSON map format. Layers are matched by name (groups by path), objects by id; renamed layers show as removed plus added.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
