# nine-slice

Preview or bake a 9-slice (9-patch) image. Give `--insets L,T,R,B` or `--center X,Y,W,H` for the stretchable middle. Corners stay 1:1, edges stretch along one axis, the centre stretches on both. Nearest-neighbour by default (`--linear` for smooth). Zero-size edge patches are skipped. A contact-sheet preview can show several target sizes at once.

## Usage

```bash
python3 nine-slice/nine_slice.py panel.png --insets 8,8,8,8 --preview panel_sizes.png --size 128x96 -o panel_128.png
python3 nine-slice/nine_slice.py panel.png --center 8,8,16,16 --sizes 64x48,96x64,192x128 --preview sheet.png
```

Run `python3 nine-slice/nine_slice.py --help` (or `gst nine-slice --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). The same 9-patch split used by Android 9-patch images and CSS `border-image`: four corners, four edges, one centre.

## Source and licence

Original code. Axis-aligned rectangles only; not a 3x3 mesh or a sliced-mesh exporter for a particular engine.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
