# tmx-decode

Expand encoded Tiled tile data (csv, base64 zlib/gzip/zstd, or XML `<tile>` children) to a plain JSON array or to csv — the inverse of tmx-encode. Accepts a Tiled JSON map (`.json` / `.tmj`) or a TMX (`.tmx` / `.xml`). All tile layers and infinite-map chunks are rewritten. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 tmx-decode/tmx_decode.py level_z.json -o level.json
python3 tmx-decode/tmx_decode.py level.tmx -o level.json
python3 tmx-decode/tmx_decode.py level.tmx -o level_csv.tmx --encoding csv
```

Run `python3 tmx-decode/tmx_decode.py --help` (or `gst tmx-decode --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap) (same as the other kit decoders). TMX cannot store a plain JSON array. This tool does not emit TMX from a JSON map. Other map features are copied through unchanged.

## Tests

`python3 -m pytest -q tests/test_batch25.py`
