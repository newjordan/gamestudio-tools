# tmx-object-types

Lint a Tiled JSON map's objects against a Tiled `objecttypes.xml` (or a JSON type schema), or apply the schema by filling in missing default properties. Existing values stay unless `--overwrite-props` is passed with apply.

## Usage

```bash
python3 tmx-object-types/tmx_object_types.py lint map.json --types objecttypes.xml
python3 tmx-object-types/tmx_object_types.py apply map.json --types objecttypes.xml -o map_filled.json
```

Run `python3 tmx-object-types/tmx_object_types.py --help` (or `gst tmx-object-types --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

XML maps (`.tmx`) are not parsed — convert with tmx-to-json first. Custom property types beyond Tiled's string/int/float/bool/color/file/object are stored as strings. Type colour from the schema is not copied onto objects (Tiled keeps it in the types file).

## Tests

`python3 -m pytest -q tests/test_batch21.py`
