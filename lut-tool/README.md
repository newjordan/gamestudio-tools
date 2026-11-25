# lut-tool

Colour-grading LUT strips: make an identity or adjusted LUT (brightness, contrast, gamma, saturation, hue, tint), apply it to an image with trilinear sampling, and convert to and from the industry `.cube` format.

## Usage

```bash
python3 lut-tool/lut_tool.py make --size 16 --contrast 1.2 --saturation 0.6 --tint '#ffaa66' --tint-amount 0.15 -o warm_lut.png
python3 lut-tool/lut_tool.py apply screenshot.png --lut warm_lut.png -o graded.png
python3 lut-tool/lut_tool.py to-cube warm_lut.png -o warm.cube   # and from-cube
```

Run `python3 lut-tool/lut_tool.py --help` (or `gst lut-tool --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. The strip layout is width N*N, height N, slice = blue, x = red, y = green (a common strip layout; check the one your engine's LUT importer expects); `.cube` is the public Adobe/Resolve text format (red-fastest). Alpha is preserved; the LUT size is a power-of-two choice you pick (16 or 32 is typical).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
