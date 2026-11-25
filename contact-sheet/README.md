# contact-sheet

Pack a folder of images into a labelled contact sheet PNG (fixed cell size, optional captions from file stems, columns, padding and background). Images are fitted with nearest-neighbour (pixel art) or bilinear scaling. `--crop-empty` trims transparent edges first. The input files are never overwritten.

## Usage

```bash
python3 contact-sheet/contact_sheet.py sprites/ -o review.png --cell 128x128 --columns 6
```

Run `python3 contact-sheet/contact_sheet.py --help` (or `gst contact-sheet --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). Complements asset-viewer and texture-resize.

## Source and licence

Original code. Captions use Pillow's default bitmap font (no complex-script shaping). Animated images contribute only the first frame. The kit's bundle excludes a root `contact_sheet.png`; this tool writes whatever `-o` you name (not that reserved file).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
