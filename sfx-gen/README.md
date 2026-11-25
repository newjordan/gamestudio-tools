# sfx-gen

sfxr-style retro sound-effect generator (coin, jump, laser, explosion, hit, powerup, blip). Seeded and batchable, it writes WAV variations plus a params JSON so you can regenerate the one you picked.

## Usage

```bash
python3 sfx-gen/sfx_gen.py coin -n 8 --seed 100 -o audio/sfx/coins
python3 sfx-gen/sfx_gen.py explosion -n 4 -o audio/sfx/boom
```

Run `python3 sfx-gen/sfx_gen.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: sfxr / bfxr / jsfxr / ChipTone.

## Source and licence

Clean-room numpy re-implementation of the sfxr parameter model (envelope, slide, vibrato, arpeggio, duty, noise). Concept credit: DrPetter's sfxr (MIT). No sfxr code copied.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
