# wav-limit

Apply a peak limiter to a PCM WAV so no sample exceeds `--ceiling-db`. A simple envelope follower with attack and release reduces gain when the signal would go over the ceiling. Length and rate stay the same; the first smpl loop is preserved.

## Usage

```bash
python3 wav-limit/wav_limit.py take.wav -o take_limited.wav --ceiling-db -0.1 --attack-ms 1 --release-ms 50
```

Run `python3 wav-limit/wav_limit.py --help` (or `gst wav-limit --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only; other RIFF chunks except a restored smpl loop are dropped on write. This is a sample-peak limiter, not a true-peak or lookahead limiter, and a stereo file uses the max of the channels as the detector. Residual overshoot from the discrete envelope is hard-clipped to the ceiling.

## Tests

`python3 -m pytest -q tests/test_batch30.py`
