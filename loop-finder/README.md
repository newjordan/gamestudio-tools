# loop-finder

Find seamless loop points in music/ambience WAVs (cross-correlation of the audio after candidate end vs start points, snapped to zero crossings), print engine loop_begin/loop_end sample values, and optionally render a crossfaded loop WAV.

## Usage

```bash
python3 loop-finder/loop_finder.py music/town.wav --json loops.json -o music/looped
# -> town.wav: loop 5.04s -> 13.04s (8.0s) score 1.0 [godot loop_begin=111153 loop_end=287553]
```

Run `python3 loop-finder/loop_finder.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: audio pipeline helpers; intended post-step for MiniMax Music exports (model already on the fleet, not run here).

## Source and licence

Original code (numpy FFT normalised cross-correlation). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
