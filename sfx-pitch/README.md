# sfx-pitch

Pitch-shift a WAV by resampling. Duration changes with pitch (a +12 semitone shift is half as long); there is no time-stretch or formant preservation. Linear interpolation; the sample rate is unchanged.

## Usage

```bash
python3 sfx-pitch/sfx_pitch.py hit.wav -o hit_up.wav --semitones 3
python3 sfx-pitch/sfx_pitch.py hit.wav -o hit_down.wav --ratio 0.5
```

Run `python3 sfx-pitch/sfx_pitch.py --help` (or `gst sfx-pitch --help`) for every option. Requires Python 3.10+ with numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Quality is linear interpolation, not a sinc resampler or phase vocoder. Pitch and duration are locked together. Multi-file batch mode is not included.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
