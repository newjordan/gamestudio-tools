# tileset-renumber

Remap local tile ids in a Tiled tileset JSON (and optionally the GIDs in one or more maps that use it). `--offset` adds N to every local id in range, or `--remap` takes a JSON/CSV table of old=new local ids (same shapes as tile-replace). Animation `tileid`s, wang tiles, and the tiles array follow the new ids. Map GIDs keep flip flags. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 tileset-renumber/tileset_renumber.py ground.tsj -o ground2.tsj --offset 10 --map level.json
```

Run `python3 tileset-renumber/tileset_renumber.py --help` (or `gst tileset-renumber --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

JSON tilesets only (convert TSX first). `--offset` walks 0..tilecount-1; ids outside that range are left alone unless listed in `--remap`. Collection tilesets with sparse ids should use `--remap`. Map matching uses `--tileset-name`, `--firstgid`, or a single tileset on the map. Encoded map layers are decoded to arrays.

## Tests

`python3 -m pytest -q tests/test_batch25.py`
