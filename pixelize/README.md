# pixelize

Turn concept art or generated images into game-ready pixel art: box/nearest downscale, palette lock (PICO-8, Game Boy, mono, or a .hex/.gpl file) or auto k-colour, optional dithering and 1px outline, upscaled preview.

## Usage

```bash
python3 pixelize/pixelize.py concept.png -o hero_px.png -w 64 -p pico8 --outline --preview-scale 4
python3 pixelize/pixelize.py bg.png -o bg_px.png -w 320 -c 24 --dither
# Lospec .hex / GIMP .gpl palettes work: -p my_palette.hex
```

Run `python3 pixelize/pixelize.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: Pixelorama (MIT), pixel-art converters (Pixel It, Lospec workflows). Good post-step for Qwen-Image 2.1 outputs once fleet wrappers exist.

## Source and licence

Original code; uses Pillow's median-cut / palette quantizer (Pillow is MIT-CMU licensed). PICO-8 and Game Boy palettes are included as colour values (facts, not code).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
