# sprite-trim

Crop transparent margins from sprites and write a bbox / trim JSON in the atlas-pack `spriteSourceSize` / `sourceSize` shape. Files, globs or a folder in; same basenames out. `--padding` keeps extra pixels around the opaque box; `--min-alpha` treats nearly-transparent pixels as empty.

## Usage

```bash
python3 sprite-trim/sprite_trim.py sprites/ -o trimmed/ --json trim.json
python3 sprite-trim/sprite_trim.py walk_01.png -o trimmed/ --padding 1
```

Run `python3 sprite-trim/sprite_trim.py --help` (or `gst sprite-trim --help`) for every option. Requires Python 3.10+ with Pillow (numpy is used when --min-alpha is greater than 1).

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Animated GIFs and already-packed atlases are not sliced; use gif-to-frames or atlas-unpack first. Pivot metadata is not rewritten.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
