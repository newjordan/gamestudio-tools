# wav-fade

Apply a linear or equal-power (sine) fade-in and/or fade-out to a PCM WAV. Overlapping fades are scaled so they meet in the middle. Uses the shared audio-tidy PCM reader.

## Usage

```bash
python3 wav-fade/wav_fade.py hit.wav -o hit_f.wav --in 0.01 --fade-out 0.05 --shape equal-power
```

Run `python3 wav-fade/wav_fade.py --help` (or `gst wav-fade --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only PCM WAVs (via audio-tidy). Fade lengths are rounded to whole samples. `--out` is the output path; use `--fade-out` or `--out-dur` for the fade-out length. Compressed or floating-point WAV is not supported.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
