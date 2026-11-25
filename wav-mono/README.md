# wav-mono

Fold a WAV (or a folder of WAVs) to mono. `--mode mix` (default) averages the channels; `left` / `right` keep one channel. Already-mono files are copied. `smpl` loop markers are preserved. Writes next to the source with `--suffix` or under `--outdir`. The input is never overwritten unless `--in-place`. PCM only, via audio-tidy.

## Usage

```bash
python3 wav-mono/wav_mono.py take.wav -o take_mono.wav
python3 wav-mono/wav_mono.py takes/ --outdir mono/ --mode left
```

Run `python3 wav-mono/wav_mono.py --help` (or `gst wav-mono --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only; other RIFF chunks except a restored `smpl` loop are dropped. More than two channels: `mix` averages all of them, `right` takes channel 2. This is the dedicated counterpart of audio-tidy's buried `--mono` flag, without the trim / fade / resample side effects.

## Tests

`python3 -m pytest -q tests/test_batch26.py`
