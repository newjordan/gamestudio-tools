# tileset-split

Split a packed Tiled tileset into two tilesets (the inverse of tileset-merge). `--at N` puts local ids 0..N-1 in A and the rest in B; `--ids` takes an explicit A-set (the rest is B); the default is a midpoint split. Image tilesets are repacked into two sheets; collection tilesets split their `tiles` arrays. Tile metadata and wangsets go with their tiles; an animation that crosses the split is dropped and reported. With `--map`, the map's tileset entry is replaced by two and GIDs are remapped when the split is not a simple prefix. Inputs are never overwritten unless `--in-place`.

## Usage

```bash
python3 tileset-split/tileset_split.py terrain.tsj -o parts/terrain --at 8
python3 tileset-split/tileset_split.py terrain.tsj -o out/ --map level.json --map-out level2.json
```

Run `python3 tileset-split/tileset_split.py --help` (or `gst tileset-split --help`) for every option. Requires Python 3.10+ (Pillow).

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

A prefix split (`--at`) leaves map GIDs unchanged and just splits the tileset entry; an arbitrary `--ids` set remaps GIDs. Animations and wang tiles that reference both halves are dropped from the output tilesets (animations are reported). Mixed image/collection tilesets are not a thing to split further — the source type is preserved. TSX input is supported; output is always JSON (`.tsj`).

## Tests

`python3 -m pytest -q tests/test_batch24.py`
