# loc-check

Validate a multi-language strings CSV: duplicate ids, missing translations, placeholder/tag/escape mismatches, untranslated copies, and length overflow (with a separate ratio for CJK). Exit 1 on errors.

## Usage

```bash
python3 loc-check/loc_check.py loc/strings.csv --source en --max-ratio 1.5
python3 loc-check/loc_check.py loc/strings.csv --strict --json loc/report.json
```

Run `python3 loc-check/loc_check.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: localisation workflows around Yarn Spinner / ink; follows pseudoloc and dialogue-extract.

## Source and licence

Original code (regex checks).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
