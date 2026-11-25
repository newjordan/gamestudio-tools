# tmx-infinite-to-finite

Convert a Tiled infinite (chunked) JSON map to a finite array map. Chunks are decoded and packed into a bounding box taken from used cells (plus `--margin`), or an explicit `--origin` / `--size`. Object positions stay in world pixels unless `--shift-objects` subtracts the new origin.

## Usage

```bash
python3 tmx-infinite-to-finite/tmx_infinite_to_finite.py infinite.json -o finite.json --margin 1 --pretty
python3 tmx-infinite-to-finite/tmx_infinite_to_finite.py infinite.json -o finite.json --origin 0,0 --size 32,32 --shift-objects
```

Run `python3 tmx-infinite-to-finite/tmx_infinite_to_finite.py --help` (or `gst tmx-infinite-to-finite --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Empty infinite maps become 1×1 unless `--size` is given. World-space image layers are not shifted.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
