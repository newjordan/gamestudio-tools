# tilemap-stats

Per-layer and per-tileset statistics for Tiled JSON maps: empty ratio, unique tile ids, flip counts, most-used tiles, object counts by type and name, unused tilesets, and empty or hidden layers. Group layers are flattened by path. Text, JSON and CSV output, with CI exit codes.

## Usage

```bash
python3 tilemap-stats/tilemap_stats.py maps/*.json --json stats.json --csv stats.csv
python3 tilemap-stats/tilemap_stats.py maps/level.json --fail-on-empty-layer --fail-on-unused-tileset
```

Run `python3 tilemap-stats/tilemap_stats.py --help` (or `gst tilemap-stats --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Complements tileset-from-image (per-tile use) and map-diff (what changed).

## Source and licence

Original code. Reads Tiled's documented JSON map format (finite and infinite maps, groups). Tile data may be a plain array or a base64 string (zlib, gzip or zstd). zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
