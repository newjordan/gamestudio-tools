# uv-check

UV sanity report for GLBs: out-of-range UVs, degenerate UV triangles, overlap between triangles (rasterised), UV coverage, and texel-density spread. Thresholds give a CI exit code.

## Usage

```bash
python3 uv-check/uv_check.py props/*.glb --max-overlap 0.05
python3 uv-check/uv_check.py hero.glb --tex-size 2048x2048 --max-density-spread 0.2
```

Run `python3 uv-check/uv_check.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Blender / glTF-Transform texturing and UV pipeline entries.

## Source and licence

Original code. Overlap is estimated on a raster (default 256 px) with triangles shrunk 12 percent, so it is approximate; mirrored UVs will count as overlap on purpose.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
