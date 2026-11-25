# sheet-pad

Add padding (and optional alpha bleed) between already-packed frames in a sprite sheet and rewrite the atlas JSON (atlas-pack / TexturePacker hash or array format). Frames are re-shelved in (y, x) order with `--pad` pixels on every side; `--keep-layout` inflates the existing positions instead. Rotated frames are refused. The input sheet and JSON are never overwritten.

## Usage

```bash
python3 sheet-pad/sheet_pad.py sheet.png sheet.json -o padded.png --pad 2 --bleed 1
python3 sheet-pad/sheet_pad.py sheet.png sheet.json -o padded.png --keep-layout --pad 1
```

Run `python3 sheet-pad/sheet_pad.py --help` (or `gst sheet-pad --help`) for every option. Requires Python 3.10+ with Pillow (uses alpha-bleed when `--bleed` is set).

## Inspiration (catalogue entry)

None (new). Complements atlas-pack, tile-extrude and alpha-bleed.

## Source and licence

Original code. Rotated frames are refused. `--keep-layout` is a rank inflation of unique x/y values, not a guarantee of a regular grid when frames were packed irregularly.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
