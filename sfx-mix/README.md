# sfx-mix

Layer several WAV files into one sound effect from a JSON recipe: offset, gain, pitch (resample), reverse, trim, fades, first-order low/high-pass and pan per layer; tail, master gain and an optional soft clip for the mix. Prints a timeline; --dry-run writes nothing.

Recipe keys: `sample_rate`, `channels`, `tail_ms`, `master_gain_db`, `peak_db`, `normalize`, `soft_clip`, and `layers`. `peak_db` (default -1) is a ceiling: the mix is turned down when it is louder and left as it is when it is quieter. `"normalize": true` also turns a quieter mix up so the peak lands on `peak_db`. `tail_ms` is silence after the last layer. Each layer may set `file` (required), `offset_ms`, `gain_db`, `pitch_semitones`, `reverse`, `trim_ms`, `fade_in_ms`, `fade_out_ms`, `lowpass_hz`, `highpass_hz` and `pan`. The same list is printed by `--help`.

## Usage

```bash
python3 sfx-mix/sfx_mix.py recipes/door_slam.json -o door_slam.wav
python3 sfx-mix/sfx_mix.py recipes/door_slam.json --dry-run
```

Run `python3 sfx-mix/sfx_mix.py --help` (or `gst sfx-mix --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Layers can come from sfx-gen or sfx-variants; check the result with wav-batch-meta and sfx-spectrogram.

## Source and licence

Original code on numpy. Pitch shifting is plain resampling (pitch and speed move together, linear interpolation); filters are 6 dB/octave. Not a DAW: no reverb, compression or time-stretching.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
