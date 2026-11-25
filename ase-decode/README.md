# ase-decode

Read a binary Aseprite `.ase` / `.aseprite` file and export composited frames as PNG plus a JSON of tags, layers and durations. Implements the public Aseprite file format so you do not need the Aseprite app.

## Usage

```bash
python3 ase-decode/ase_decode.py hero.aseprite -o frames --json ase.json
```

Run `python3 ase-decode/ase_decode.py --help` (or `gst ase-decode --help`) for every option. Requires Python 3.10+ and Pillow.

## Inspiration (catalogue entry)

None (new). Aseprite file format spec (https://github.com/aseprite/aseprite/blob/main/docs/ase-file-specs.md).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

16-bit grayscale and tilemap cels are detected and reported but not composited. Group layers are skipped (their children still composite). Blend modes other than normal are treated as normal. External files and user-data chunks are ignored.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
