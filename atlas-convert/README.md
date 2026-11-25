# atlas-convert

Convert atlas-pack JSON to TexturePacker array/hash, libGDX .atlas, Starling XML, or CSS sprite classes, carrying trim data through.

## Usage

```bash
python3 atlas-convert/atlas_convert.py art/player.json --to libgdx -o art/player.atlas
python3 atlas-convert/atlas_convert.py art/player.json --to starling -o art/player.xml --image player.png
```

Run `python3 atlas-convert/atlas_convert.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: atlas/texture-packer tooling (free-tex-packer, libGDX packer).

## Source and licence

Original code following the public libGDX TextureAtlas and Starling atlas format docs. Not yet loaded into libGDX/Starling itself; output matches the documented layout.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
