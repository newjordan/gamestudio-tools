# lit-preview

See a sprite with its normal map lit: Lambert diffuse plus optional specular from point or directional, coloured lights, with an orbiting-light GIF mode and a DirectX/OpenGL green flip.

## Usage

```bash
python3 lit-preview/lit_preview.py hero.png hero_n.png -o lit.png --light 4,4,12,#ffeecc --spec 0.4
python3 lit-preview/lit_preview.py hero.png hero_n.png -o orbit.gif --orbit 16
```

Run `python3 lit-preview/lit_preview.py --help` (or `gst lit-preview --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

DeepBump (normal map workflows).

## Source and licence

Original code. A preview, not an engine's lighting model: no shadows, light falloff or tone mapping.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
