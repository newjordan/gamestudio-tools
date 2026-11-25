# wav-gap-squeeze

Shrink interior silences longer than `--min-ms` down to `--cap-ms` (dialogue cleanup). Leading and trailing silence is left alone (use wav-trim for those). A fully silent file is skipped unless `--keep-silent`. Inputs may be files or folders. The input path is never overwritten. PCM only, via audio-tidy.

## Usage

```bash
python3 wav-gap-squeeze/wav_gap_squeeze.py vo/*.wav --outdir tight/ --min-ms 400 --cap-ms 150 --json report.json
```

Run `python3 wav-gap-squeeze/wav_gap_squeeze.py --help` (or `gst wav-gap-squeeze --help`) for every option. Requires Python 3.10+ with numpy (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). Complements wav-trim, wav-split-silence and wav-chan-split.

## Source and licence

Original code. PCM WAV only; other RIFF chunks are not copied. This is a peak-threshold gap squeeze, not a VAD or sentence segmenter.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
