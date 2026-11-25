# texture-resize

Batch-resize images to a max edge, a power-of-two, and/or a multiple-of-N, with a before/after report. Default filter is nearest-neighbour (`--linear` for bilinear). Does not upscale unless `--allow-upscale`. `--pot` rounds each side down to the previous power of two (`--pot-up` to go up). Writes into `--outdir` under the same names; refuses to overwrite inputs in place.

## Usage

```bash
python3 texture-resize/texture_resize.py textures/ -o textures_1k/ --max 1024 --pot --json resize.json
python3 texture-resize/texture_resize.py ui/*.png -o ui_snap/ --multiple 4
```

Run `python3 texture-resize/texture_resize.py --help` (or `gst texture-resize --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). Complements asset-lint (which flags oversize or non-POT textures but does not resize them).

## Source and licence

Original code. No mip-chain or KTX/Basis output; this is a PNG/JPEG/WebP/etc. resize.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
