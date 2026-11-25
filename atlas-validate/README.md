# atlas-validate

Check an atlas JSON against its PNG: frames outside the image, overlaps, duplicate names, transparent frames, frames closer than the padding (texture bleed), inconsistent trim data, non-power-of-two sizes and wasted area.

## Usage

```bash
python3 atlas-validate/atlas_validate.py atlas.json --padding 2 --strict
```

Run `python3 atlas-validate/atlas_validate.py --help` (or `gst atlas-validate --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with atlas-pack and atlas-convert.

## Source and licence

Original code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
