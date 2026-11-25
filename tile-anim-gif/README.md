# tile-anim-gif

Render Tiled `tiles[].animation` entries to per-tile GIFs, and optionally a map preview GIF (via tile-preview) that honours flip flags and advances on `--tick-ms`. Input is a Tiled map JSON or a tileset JSON. `--image` overrides the tileset PNG (an existing path is used as-is; otherwise it is resolved next to the JSON).

## Usage

```bash
python3 tile-anim-gif/tile_anim_gif.py tilesets/water.json -o preview/water --scale 3
python3 tile-anim-gif/tile_anim_gif.py maps/cave.json -o preview/cave --tick-ms 200 --duration-ms 1600 --scale 1
```

Run `python3 tile-anim-gif/tile_anim_gif.py --help` (or `gst tile-anim-gif --help`) for every option. Requires Python 3.10+ with Pillow (uses tile-preview to draw the map).

## Inspiration (catalogue entry)

None (new). Reads Tiled's documented tile-animation format (`tileid` + `duration` in milliseconds). Complements tile-preview (static maps) and spritesheet-gif (sprite clips).

## Source and licence

Original code. External `.tsx` / `.tsj` tilesets (a map's `source`, or a `.tsx` file as input) are resolved next to the tileset file. zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap). The map GIF is finite orthogonal only (same limits as tile-preview). Duration defaults to the LCM of animation cycles, capped at 8 s.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
