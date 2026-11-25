# tmx-encode

Re-encode Tiled tile data as csv, a plain JSON array, or base64 with zlib / gzip / (when available) zstd — the inverse of the kit's decoders. Accepts a Tiled JSON map (`.json` / `.tmj`) or a TMX (`.tmx` / `.xml`). All tile layers and infinite-map chunks are rewritten. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 tmx-encode/tmx_encode.py level.json -o level_z.json --encoding base64 --compression zlib
python3 tmx-encode/tmx_encode.py level.json -o level.csv.json --encoding csv
python3 tmx-encode/tmx_encode.py level.tmx -o level.tmx --encoding csv --in-place
```

Run `python3 tmx-encode/tmx_encode.py --help` (or `gst tmx-encode --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

zstd is offered only when `compression.zstd` (Python 3.14+), `pyzstd`, or `zstd` can compress; if none of those are installed, writing zstd is refused with a one-line error naming them. (Reading zstd needs none of them: the kit decodes it itself since 2.1.0.) TMX cannot store a plain JSON array. CSV in TMX is written as a single comma list when the layer width is not on the `<data>` element. Other map features (objects, tilesets, properties) are copied through unchanged.

## Tests

`python3 -m pytest -q tests/test_batch24.py`
