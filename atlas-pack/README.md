# atlas-pack

Pack a folder of sprites into one power-of-two texture atlas (PNG) plus a TexturePacker-style JSON frame map, with alpha trimming and padding.

## Usage

```bash
python3 atlas-pack/atlas_pack.py art/sprites -o build_art/player_atlas --padding 2
# -> player_atlas.png + player_atlas.json (frames/x/y/w/h, trimmed, sourceSize)
# options: --max 4096  --no-trim  --no-pot
```

Run `python3 atlas-pack/atlas_pack.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: texture-packer / atlas tools (free-tex-packer, crunch, TexturePacker workflow).

## Source and licence

Original code. MaxRects best-short-side-fit algorithm from Jukka Jylänki, *A Thousand Ways to Pack the Bin* (2010, freely published paper; the algorithm is not copyrighted). The JSON layout follows the widely used TexturePacker 'hash' shape so Phaser/Pixi/Godot importers read it. No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
