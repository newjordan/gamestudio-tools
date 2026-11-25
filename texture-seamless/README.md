# texture-seamless

Make a texture tile without visible seams (half-size offset plus a smooth blend window), print a before/after seam score, and write a 2x2 tiled preview.

## Usage

```bash
python3 texture-seamless/texture_seamless.py rock.png -o rock_tile.png --preview rock_preview.png --power 1.5
```

Run `python3 texture-seamless/texture_seamless.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: texturing tools (Materialize, Ucupaint); feed the result to normal-bake and channel-pack.

## Source and licence

Original code. Offset-and-blend is a standard texturing technique; busy photographic textures can show mild ghosting in the centre cross.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
