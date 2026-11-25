# wav-invert

Invert the polarity of a WAV (or a folder of WAVs) by multiplying samples by -1. `smpl` loop markers are preserved. Writes next to the source with `--suffix` or under `--outdir`. The input is never overwritten unless `--in-place`. PCM only, via audio-tidy.

## Usage

```bash
python3 wav-invert/wav_invert.py take.wav -o take_inv.wav
```

Run `python3 wav-invert/wav_invert.py --help` (or `gst wav-invert --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only; other RIFF chunks except a restored `smpl` loop are dropped by audio-tidy. Two inversions cancel. A DC offset, if present, changes sign (run wav-dc-remove first if that matters).

## Tests

`python3 -m pytest -q tests/test_batch26.py`
