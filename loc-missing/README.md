# loc-missing

List localisation keys that have a source-language string but are blank or absent in one or more other language columns. Default source is `en`. Exits 1 when anything is missing (use `--no-fail` for a report-only run). `--format json|csv|text` picks the stdout/file shape. Sibling of loc-check, focused on missing rather than placeholders or length.

## Usage

```bash
python3 loc-missing/loc_missing.py loc/strings.csv --source en
python3 loc-missing/loc_missing.py loc/strings.csv --langs fr,de -o missing.json --format json --no-fail
```

Keys with an empty source cell are skipped (they are not "missing translations"). Run `python3 loc-missing/loc_missing.py --help` (or `gst loc-missing --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements loc-check, loc-placeholder-lint and loc-fit.

## Source and licence

Original code. The CSV is utf-8 with optional BOM. Non-language columns (`notes`, `comment`, `context`, `max`, `max_len`) are ignored when auto-detecting targets.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
