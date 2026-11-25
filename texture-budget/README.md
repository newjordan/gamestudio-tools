# texture-budget

Scan a folder of textures and report estimated GPU memory (`width * height * bytes-per-pixel`, plus a 1/3 mip-chain estimate unless `--no-mips`). Flags NPOT sizes and edges over `--max-edge`. Optional `--fail-over-mb` exits 1 when the total exceeds a budget.

## Usage

```bash
python3 texture-budget/texture_budget.py ./art --json vram.json --fail-over-mb 256
```

Run `python3 texture-budget/texture_budget.py --help` (or `gst texture-budget --help`) for every option. Requires Python 3.10+ and Pillow.

## Inspiration (catalogue entry)

None (new). Complements level-budget for texture VRAM rather than map objects.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Estimate only: it does not inspect GPU-compressed formats (DXT/ETC/ASTC) or Godot import settings (sRGB, mip, resize). Animated GIFs use the first-frame size. Array / cubemap packing is not modelled.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
