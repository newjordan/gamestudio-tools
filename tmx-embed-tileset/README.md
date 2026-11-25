# tmx-embed-tileset

Inline external Tiled tilesets (`.tsx` / `.tsj` / `.json`) into a Tiled JSON map so it is self-contained. `firstgid` from the map wins. Image paths inside the external file are rewritten relative to the output map (pass `--abs-images` to keep the absolute paths the resolver produced).

```
gst tmx-embed-tileset level.json -o level_embedded.json --pretty
```

## Usage

```bash
python3 tmx-embed-tileset/tmx_embed_tileset.py level.json -o level_embedded.json --pretty
```

Run `python3 tmx-embed-tileset/tmx_embed_tileset.py --help` (or `gst tmx-embed-tileset --help`) for every option. Requires Python 3.10+.

## Known gaps

zstd-encoded tile *data* is decoded as in the other kit readers (this tool does not rewrite layer data, only tilesets). Wang sets and terrain from `.tsx` follow whatever `map_diff.load_tsx` currently copies.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
