# particle-preview

Bake a simple 2D particle burst (or a short stream with `--rate`) to a review GIF. Particles get a heading and spray, a speed range, gravity and a lifetime. A `--sprite` PNG is drawn nearest-neighbour (optional rotation along velocity); otherwise square pixels or `--circle`. Seeded, CPU only. Palette GIF flattened onto `--bg`.

## Usage

```bash
python3 particle-preview/particle_preview.py -o burst.gif --count 24 --gravity 180 --spray 50 --lifetime-ms 800
python3 particle-preview/particle_preview.py -o stream.gif --rate 40 --frames 32 --sprite spark.png --rotate-sprite
```

Run `python3 particle-preview/particle_preview.py --help` (or `gst particle-preview --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). A review-link stand-in, not a runtime particle system or an Effekseer exporter.

## Source and licence

Original code. The physics is a simple kinematic burst (no collisions, no turbulence).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
