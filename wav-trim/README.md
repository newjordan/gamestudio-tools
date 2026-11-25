# wav-trim

Trim leading and trailing silence from WAV files and write trimmed copies plus a before/after report (lead/trail ms, durations). Uses the same peak-threshold rule as wav-batch-meta (default `--thresh-db -60`) with an optional pad of kept silence. Mid-file silences are left alone. Fully silent files are not written unless `--keep-silent`. The input path is never overwritten.

## Usage

```bash
python3 wav-trim/wav_trim.py takes/*.wav --outdir trimmed/ --json report.json
python3 wav-trim/wav_trim.py vo/line.wav --suffix _trim --pad-ms 20 --dry-run
```

Run `python3 wav-trim/wav_trim.py --help` (or `gst wav-trim --help`) for every option. Requires Python 3.10+ with numpy (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). Complements wav-batch-meta (which reports lead/trail silence but does not write a trimmed file) and audio-tidy (which trims as part of a broader clean pass, default threshold -50 dB).

## Source and licence

Original code. PCM WAV only; other RIFF chunks are not copied onto the output.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
