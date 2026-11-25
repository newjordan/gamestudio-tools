# vo-diff

Diff two dialogue CSVs (from dialogue-extract) and list exactly what needs (re)recording: added, removed, changed, minor-edit and speaker-changed lines, re-record minutes per speaker, and lines with no audio file yet.

## Usage

```bash
python3 vo-diff/vo_diff.py loc/lines_v1.csv loc/lines_v2.csv -o vo/todo.csv --audio-dir vo/recordings --json vo/diff.json
# IMPORTANT: run `dialogue-extract --tag-in-place` once first so ids stay stable; auto-generated ids are hashes of the text and change when the text changes.
```

Run `python3 vo-diff/vo_diff.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Yarn Spinner / ink localisation workflows.

## Source and licence

Original code (difflib from the Python standard library).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
