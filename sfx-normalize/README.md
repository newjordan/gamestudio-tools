# sfx-normalize

Peak-normalise a WAV (or a folder of WAVs) to a target peak dBFS (default `-1.0`), or, with `--lufs`, to a target integrated LUFS capped so the true peak stays under `--max-true-peak` (the same uncertified ITU-R BS.1770-4 meter as wav-batch-meta / wav-loud-apply). Silent files are left unchanged and reported. `smpl` loop markers are preserved. Writes next to the source with `--suffix` or under `--outdir`. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 sfx-normalize/sfx_normalize.py hit.wav -o hit_n.wav --peak -1
python3 sfx-normalize/sfx_normalize.py sfx/ --outdir nrm/ --peak -0.1 --json report.json
python3 sfx-normalize/sfx_normalize.py hit.wav -o hit_lufs.wav --lufs -16 --max-true-peak -1
```

Run `python3 sfx-normalize/sfx_normalize.py --help` (or `gst sfx-normalize --help`) for every option. Requires Python 3.10+ (numpy; PCM via audio-tidy).

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

The default remains a sample peak, not LUFS. `--lufs` uses the same uncertified meter as wav-batch-meta (no surround weights; files under 400 ms are un-gated and flagged short). PCM only; other RIFF chunks except a restored `smpl` loop are dropped by audio-tidy. A 0 dBFS peak target may be clipped by a fraction of an LSB after integer quantisation. `--lufs` and `--peak` are not mixed: when `--lufs` is set, `--peak` is ignored.

## Tests

`python3 -m pytest -q tests/test_batch24.py tests/test_batch25.py`
