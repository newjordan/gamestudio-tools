# wav-batch-meta

Loudness and technical report for many WAV files against a target: integrated LUFS (ITU-R BS.1770-4 with gating), max momentary loudness, sample and true peak, RMS, crest, DC offset, clipping, leading and trailing silence. Per-folder targets, suggested gain capped by the true-peak ceiling, CSV/JSON output and a CI exit code.

## Usage

```bash
python3 wav-batch-meta/wav_batch_meta.py audio/ --target -16 --csv loudness.csv
python3 wav-batch-meta/wav_batch_meta.py audio/ --rule 'music/*=-16' --rule 'sfx/*=-18' --max-true-peak -1
```

Run `python3 wav-batch-meta/wav_batch_meta.py --help` (or `gst wav-batch-meta --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Extends audio-tidy's report; apply the suggested gain with audio-tidy.

## Source and licence

Original code implementing the published ITU-R BS.1770-4 algorithm (K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU relative gates). The filter coefficients are derived per sample rate and checked against the published 48 kHz values; the test suite checks the EBU Tech 3341 reference (stereo 1 kHz at -23 dBFS reads -23.0 LUFS). Not a certified meter. Surround weighting is not implemented.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
