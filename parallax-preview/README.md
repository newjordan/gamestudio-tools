# parallax-preview

Scrolling parallax GIF from layer PNGs, back to front, with a per-layer speed (`x` or `x:y`), wrap, and a set camera travel (`--pixels`, optional `--pixels-y`). Speeds default to a ramp from 0 (back) to 1 (front). Optionally write the first frame as a PNG.

## Usage

```bash
python3 parallax-preview/parallax_preview.py sky.png hills.png ground.png -o parallax.gif --speeds 0.15,0.5,1 --width 256 --height 144 --frames 48 --fps 12
python3 parallax-preview/parallax_preview.py far.png near.png -o p.gif --speeds 0.2:0,1:0.1 --pixels 256 --png frame0.png
```

Run `python3 parallax-preview/parallax_preview.py --help` (or `gst parallax-preview --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). A review-link stand-in for the classic side-scroller / camera-scroll preview, not a runtime parallax controller.

## Source and licence

Original code. Layers wrap as repeating strips (the image is tiled). Palette GIFs are flattened onto `--bg`.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
