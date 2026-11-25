# curve-gen

Control points to smooth paths: centripetal Catmull-Rom (through the points), Bezier, or linear; open or closed, 2D or 3D; constant-speed resampling or fixed counts; JSON/CSV with arc length and tangents, and an SVG preview.

## Usage

```bash
python3 curve-gen/curve_gen.py --points '0,0;40,30;80,0;120,40' --spacing 8 --json path.json --csv path.csv --svg path.svg
```

Run `python3 curve-gen/curve_gen.py --help` (or `gst curve-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Catmull-Rom uses the standard Barry-Goldman pyramid formulation.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
