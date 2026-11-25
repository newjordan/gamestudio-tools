# normal-fix

Check and repair tangent-space normal maps: renormalise, flip green (OpenGL/DirectX), flip red, scale strength, rebuild blue from red and green (two-channel maps), clamp into-surface vectors, make empty mid-grey texels flat, keep or force alpha.

## Usage

```bash
python3 normal-fix/normal_fix.py check maps/*.png --max-error 0.05
python3 normal-fix/normal_fix.py fix maps/*.png -o fixed/ --flip-green
```

Run `python3 normal-fix/normal_fix.py --help` (or `gst normal-fix --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

DeepBump and Ucupaint (normal map workflows).

## Source and licence

Original code; standard vector maths. The DirectX/OpenGL convention cannot be detected from pixels, so flipping is always your explicit choice.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
