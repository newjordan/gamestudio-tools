# sfx-variants

Make N seeded variations of one sound (random pitch via resampling, gain, small start offset, fades, peak limit) so repeated effects do not sound identical.

## Usage

```bash
python3 sfx-variants/sfx_variants.py audio/footstep.wav -o audio/footsteps -n 6 --seed 20 --semitones 1.5 --offset-ms 15
```

Run `python3 sfx-variants/sfx_variants.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: audio pipeline; companion to sfx-gen (which makes the base sound).

## Source and licence

Original code (numpy linear resampling).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
