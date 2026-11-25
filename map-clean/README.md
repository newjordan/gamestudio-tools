# map-clean

Drop hidden layers, empty tile/object/image/group layers, unused tilesets, and empty property lists from a Tiled JSON map. Remaining tilesets are packed to tight firstgids and every tile-layer GID and object `gid` is remapped (flip flags kept). Pass `--keep-firstgids` to leave the original firstgids and cell values alone. Refuses to overwrite the input. Pretty or compact JSON out.

## Usage

```bash
python3 map-clean/map_clean.py maps/level.json -o maps/level.clean.json --pretty
python3 map-clean/map_clean.py maps/level.json -o maps/level.clean.json --keep-hidden --keep-firstgids
```

Run `python3 map-clean/map_clean.py --help` (or `gst map-clean --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements tilemap-stats (what is unused) and tileset-from-image (per-tile use). A cleanup pass that also packs firstgids unless `--keep-firstgids` is set.

## Source and licence

Original code. Reads Tiled's documented JSON map format (finite maps; group layers are walked). Encoded (base64 zlib/gzip or csv) tile data is decoded to plain arrays in the output. zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap). Remaining tilesets are packed to tight firstgids and tile-layer / object GIDs are remapped (flip flags kept). Pass --keep-firstgids to leave the original firstgids and cell values alone.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
