# dungeon-gen

Seeded roguelike layouts, either BSP rooms + corridors or cellular-automata caves (always one connected region), exported as ASCII, PNG and Tiled-compatible JSON (1 floor, 2 wall).

## Usage

```bash
python3 dungeon-gen/dungeon_gen.py --mode bsp --size 64x40 --seed 7 -o levels/crypt_07
python3 dungeon-gen/dungeon_gen.py --mode caves --size 96x64 --seed 3 -o levels/cave_03
```

Run `python3 dungeon-gen/dungeon_gen.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

Since 2.5.0 the JSON map embeds a two-tile tileset (`<out>_tiles.png`: floor id 0, wall id 1 with
`solid=true`), layer ids, and in BSP mode a `rooms` object layer (one `room` rectangle per room with index,
cx, cy, w, h), so map-to-godot, map-reach (`--solid-ids 2`), nav-to-godot and map-auto-layer can use it directly.
`--tile` sets the tile size (default 16).

## Inspiration (catalogue entry)

Catalogue: Tiled / LDtk level pipelines, RogueBasin generators.

## Source and licence

Original code. BSP-dungeon and the 4-5 cellular-automata cave rule are textbook public techniques (RogueBasin). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
