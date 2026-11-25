# sprite-fx

Bake outline, drop shadow and hit-flash variants into sprites or whole frame folders, padding every output equally so animation frames stay aligned.

## Usage

```bash
python3 sprite-fx/sprite_fx.py frames/hero_walk -o frames/hero_walk_fx --outline 1 --outline-color 101020 --shadow 2,2,0.5,1 --flash
```

Run `python3 sprite-fx/sprite_fx.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: sprite post-processing steps from Aseprite / Pixelorama style workflows.

## Source and licence

Original code. No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
