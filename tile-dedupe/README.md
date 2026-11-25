# tile-dedupe

Find duplicate and empty tiles in a tileset (optionally treating flips and rotations as duplicates), write a compacted tileset plus a remap JSON, and optionally rewrite a Tiled map with the right flip flags.

## Usage

```bash
python3 tile-dedupe/tile_dedupe.py tiles.png --tile 16x16 --transforms -o tiles_compact --map level.json --map-out level_compact.json
```

Run `python3 tile-dedupe/tile_dedupe.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Tiled / LDtk tileset hygiene; follow with tile-extrude.

## Source and licence

Original code. Tiled flip-flag semantics (diagonal, then horizontal, then vertical) follow its public map-format docs and are checked by a test for all 8 transforms. Map rewrite refuses an already-flagged tile that becomes a transformed duplicate.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
