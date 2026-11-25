# wav-dc-remove

Strip DC offset from PCM WAVs by subtracting each channel's mean, writing new files and a before/after report (DC, peak). Inputs may be files or folders. The input path is never overwritten (pass `--outdir` or `--suffix`). PCM only, via audio-tidy; other RIFF chunks are dropped.

## Usage

```bash
python3 wav-dc-remove/wav_dc_remove.py takes/ -o cleaned/ --json report.json
python3 wav-dc-remove/wav_dc_remove.py vo.wav --suffix _dc --csv report.csv
```

Run `python3 wav-dc-remove/wav_dc_remove.py --help` (or `gst wav-dc-remove --help`) for every option. Requires Python 3.10+ with numpy.

## Inspiration (catalogue entry)

None (new). Complements audio-tidy, wav-trim and wav-loud-apply.

## Source and licence

Original code. Mean is computed on the decoded float signal; a perfectly centred file still gets a rewrite. Not a high-pass filter.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
