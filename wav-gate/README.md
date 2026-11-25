# wav-gate

Apply a noise gate to a PCM WAV. Samples below --thresh-db are faded toward silence with optional attack, hold and release. Length and rate stay the same; the first smpl loop is preserved.

## Usage

```bash
python3 wav-gate/wav_gate.py take.wav -o take_gated.wav --thresh-db -40 --attack-ms 5 --hold-ms 20 --release-ms 50
```

Run `python3 wav-gate/wav_gate.py --help` (or `gst wav-gate --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only; other RIFF chunks except a restored smpl loop are dropped on write. The envelope is a simple per-sample ramp, not a DAW-quality detector, and a stereo file uses the max of the channels as the detector.

## Tests

`python3 -m pytest -q tests/test_batch29.py`
