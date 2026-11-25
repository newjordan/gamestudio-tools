# wav-resample

Change a WAV's sample rate with linear interpolation (via audio-tidy). `smpl` loop markers are scaled by the rate ratio and clamped to the new length. PCM only. Writes next to the source with `--suffix` or under `--outdir`. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 wav-resample/wav_resample.py vo.wav -o vo_48k.wav --rate 48000
python3 wav-resample/wav_resample.py sfx/ --outdir out/ --rate 22050 --suffix _22k
```

Run `python3 wav-resample/wav_resample.py --help` (or `gst wav-resample --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Linear interpolation, not a polyphase or band-limited resampler, so large downsamples can alias. PCM only; other RIFF chunks except a restored `smpl` loop are dropped by audio-tidy. Only the first `smpl` loop is rewritten.

## Tests

`python3 -m pytest -q tests/test_batch25.py`
