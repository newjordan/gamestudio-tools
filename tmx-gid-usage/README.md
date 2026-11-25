# tmx-gid-usage

Count GID usage in a Tiled JSON map. Reports per GID (tileset name, local id, flip-flag counts) and unused tiles in each tileset. Encoded layers are decoded first. Optional `--fail-on-unused-tileset` exits 1 when a tileset has no used tiles. The input is never overwritten unless `--in-place` (only relevant for `--json` / `-o`).

## Usage

```bash
python3 tmx-gid-usage/tmx_gid_usage.py level.json --json usage.json
python3 tmx-gid-usage/tmx_gid_usage.py level.json -o usage.csv --fail-on-unused-tileset
```

Run `python3 tmx-gid-usage/tmx_gid_usage.py --help` (or `gst tmx-gid-usage --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

JSON maps only (convert a TMX first). Object tiles (gid on objects) are not counted — only tile layers. Unused-tile lists need a tileset `tilecount`. Flip flags are counted but the GID in the report is the unflagged id.

## Tests

`python3 -m pytest -q tests/test_batch28.py`
