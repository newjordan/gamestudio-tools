# tmx-layer-filter

Keep or drop Tiled JSON layers by name glob (`--keep` or `--drop`, comma-separated, fnmatch). Group layers are walked: a group is kept if it matches or if any child is kept. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 tmx-layer-filter/tmx_layer_filter.py level.json -o fg.json --keep 'fg_*,objs'
python3 tmx-layer-filter/tmx_layer_filter.py level.json -o clean.json --drop 'tmp_*,scratch'
```

Run `python3 tmx-layer-filter/tmx_layer_filter.py --help` (or `gst tmx-layer-filter --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

JSON maps only (convert a TMX first). Matching is case-sensitive with `fnmatch` (`*` and `?`). Layer contents are not rewritten. An empty result is refused unless `--allow-empty`.

## Tests

`python3 -m pytest -q tests/test_batch27.py`
