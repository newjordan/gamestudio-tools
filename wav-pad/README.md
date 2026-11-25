# wav-pad

Pad a PCM WAV with leading and/or trailing silence, or out to a target duration (`--center` splits the extra silence on both sides). Already-long files are left at their current length. Uses the shared audio-tidy PCM reader.

## Usage

```bash
python3 wav-pad/wav_pad.py hit.wav -o hit_1s.wav --to-duration 1.0 --center
```

Run `python3 wav-pad/wav_pad.py --help` (or `gst wav-pad --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only PCM WAVs (via audio-tidy). Padding is exact to the nearest sample. Existing loop metadata (smpl) is not rewritten for the new length — run wav-loop-meta afterwards if you need a loop cue.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
