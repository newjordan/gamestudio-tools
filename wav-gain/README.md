# wav-gain

Apply a fixed dB gain to a WAV (or a folder of WAVs). Optional `--max-true-peak` caps the gain so the 4x-oversampled true peak stays under a ceiling (the same uncertified meter as wav-batch-meta). `smpl` loop markers are preserved. Writes next to the source with `--suffix` or under `--outdir`. The input is never overwritten unless `--in-place`. PCM only, via audio-tidy.

## Usage

```bash
python3 wav-gain/wav_gain.py take.wav -o take_down.wav --gain -3
python3 wav-gain/wav_gain.py takes/ --outdir out/ --gain 6 --max-true-peak -1
```

Run `python3 wav-gain/wav_gain.py --help` (or `gst wav-gain --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

This is a fixed gain, not a LUFS or peak normaliser (use sfx-normalize / wav-loud-apply for those). The true-peak cap uses the same uncertified meter as wav-batch-meta. PCM only; other RIFF chunks except a restored `smpl` loop are dropped.

## Tests

`python3 -m pytest -q tests/test_batch27.py`
