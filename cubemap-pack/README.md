# cubemap-pack

Pack six cube faces (`px`, `nx`, `py`, `ny`, `pz`, `nz`) into a horizontal strip, a vertical strip, or a vertical cross, and unpack a strip or cross back to six PNGs. All faces must be square and the same size. Unpack detects the layout from the aspect ratio (6×1, 1×6, or 4×3) unless `--layout` is given.

Vertical cross layout (4×3 cells):

```
    py
nx  pz  px  nz
    ny
```

```
gst cubemap-pack pack --px px.png --nx nx.png --py py.png --ny ny.png --pz pz.png --nz nz.png -o cube.png --layout cross
gst cubemap-pack unpack cube.png -o faces/
```

## Usage

```bash
python3 cubemap-pack/cubemap_pack.py pack --px px.png --nx nx.png --py py.png --ny ny.png --pz pz.png --nz nz.png -o cube.png --layout cross
python3 cubemap-pack/cubemap_pack.py unpack cube.png -o faces/
```

Run `python3 cubemap-pack/cubemap_pack.py --help` (or `gst cubemap-pack --help`) for every option. Requires Python 3.10+ with Pillow.

## Known gaps

Horizontal and latitude-longitude (equirectangular) projections are not packed or unpacked. Face-name aliases (left/right/front, +X, posx) are not accepted — use px/nx/py/ny/pz/nz.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
