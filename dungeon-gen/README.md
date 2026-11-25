# dungeon-gen

Seeded roguelike layouts, either BSP rooms + corridors or cellular-automata caves (always one connected region), exported as ASCII, PNG and Tiled-compatible JSON (1 floor, 2 wall).

## Usage

```bash
python3 dungeon-gen/dungeon_gen.py --mode bsp --size 64x40 --seed 7 -o levels/crypt_07
python3 dungeon-gen/dungeon_gen.py --mode caves --size 96x64 --seed 3 -o levels/cave_03
```

Run `python3 dungeon-gen/dungeon_gen.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: Tiled / LDtk level pipelines, RogueBasin generators.

## Source and licence

Original code. BSP-dungeon and the 4-5 cellular-automata cave rule are textbook public techniques (RogueBasin). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
