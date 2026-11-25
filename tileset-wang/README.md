# tileset-wang

Write a Tiled tileset JSON with a wang set so Tiled can terrain-paint from an autotile-gen (16-tile edge) or tileset-gen (47-tile blob) sheet. Colour 1 is the inner terrain; 0 is none. The blob set is `mixed` (edge+corner) in tileset-gen CANON order; the 16-tile set is `edge` in bitmask order. Input is a meta JSON, a Tiled tileset JSON (wangsets are added), or `--kind blob|edge` with `--image`. The input is never overwritten.

## Usage

```bash
python3 tileset-wang/tileset_wang.py grass.json -o grass.tsj --image grass.png
python3 tileset-wang/tileset_wang.py --kind edge --image water.png -o water.tsj
```

Run `python3 tileset-wang/tileset_wang.py --help` (or `gst tileset-wang --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements tileset-gen and autotile-gen.

## Source and licence

Original code from the documented Tiled JSON wang-set layout. Terrain probability and multi-colour wang sets are not generated; Godot terrain sets are a different format (see godot-tileset).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
