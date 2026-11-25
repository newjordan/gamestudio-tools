# atlas-sort

Sort frames in a TexturePacker-style atlas JSON by name, position or size. The sheet image is not rewritten. Hash-object key order or array order is updated.

## Usage

```bash
python3 atlas-sort/atlas_sort.py sheet.json -o sheet_sorted.json --by name
```

Run `python3 atlas-sort/atlas_sort.py --help` (or `gst atlas-sort --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Sort is stable only as a tie-break on the frame name. The packed pixels are not re-laid out (use atlas-pack to actually repack). Hash JSON relies on insertion-order objects (Python 3.7+).

## Tests

`python3 -m pytest -q tests/test_batch29.py`
