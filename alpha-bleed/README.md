# alpha-bleed

Fix dark or light fringes around sprites that get filtered or mip-mapped: copy the nearest opaque colours outward into fully transparent pixels (RGB only, alpha never touched, so the picture looks identical). Repeated 8-neighbour dilation up to --distance passes; files or folders in, same names out.

## Usage

```bash
python3 alpha-bleed/alpha_bleed.py sprites/ -o sprites_bled/
python3 alpha-bleed/alpha_bleed.py hero.png -o hero_bled.png --distance 8 --threshold 0
```

Run `python3 alpha-bleed/alpha_bleed.py --help` (or `gst alpha-bleed --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Run it before atlas-pack or sprite-sheet-optimize when sprites will be scaled or filtered; tile-extrude does the equivalent for tile edges.

## Source and licence

Original code on Pillow and numpy; the technique (alpha bleeding / edge padding) is long-standing practice in texture packers. Does not un-premultiply or fix halos baked into semi-transparent pixels.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
