# ldtk-to-csv

Export LDtk projects to CSV (IntGrid values, tile ids, entities with fields) and, optionally, a Tiled-style JSON map per level; handles externally saved level files.

## Usage

```bash
python3 ldtk-to-csv/ldtk_to_csv.py project.ldtk -o csv/ --tiled
python3 ldtk-to-csv/ldtk_to_csv.py project.ldtk -o csv/ --levels-dir project/
```

Run `python3 ldtk-to-csv/ldtk_to_csv.py --help` (or `gst ldtk-to-csv --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

LDtk (level editor) and Tiled.

## Source and licence

Original code from the public LDtk JSON docs. Tile flips and offsets are not carried across; ids are tileset tile id + 1 (0 = empty).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
