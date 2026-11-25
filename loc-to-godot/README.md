# loc-to-godot

Write a Godot 4 translation CSV from a kit localisation CSV. The first column is the key (`id` by default) and the header row is the list of locales, which is the layout Godot's importer expects. Optional `--translation-dir` also writes one Translation resource per locale.

When `GODOT_BIN` or `--godot` points at a Godot 4 editor, the tool runs a headless CSV import (verified with official Godot 4.7.2) and copies the official `.translation` files (OptimizedTranslation). Without Godot it writes a text `.tres` of type Translation instead, which the same editor can load.

## Usage

```bash
python3 loc-to-godot/loc_to_godot.py strings.csv -o translations.csv --translation-dir ./i18n --json report.json
```

Run `python3 loc-to-godot/loc_to_godot.py --help` (or `gst loc-to-godot --help`) for every option. Requires Python 3.10+. Official `.translation` binaries need a Godot 4 editor (`GODOT_BIN`).

## Inspiration (catalogue entry)

None (new). Godot 4 "Internationalizing games" CSV layout.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Duplicate keys after the first are skipped. Plural / ICU forms are not expanded. The `.tres` fallback is a plain Translation, not an OptimizedTranslation. Headless import is isolated (temporary HOME / XDG) and needs a few seconds.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
