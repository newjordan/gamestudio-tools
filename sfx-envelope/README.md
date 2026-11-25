# sfx-envelope

Apply an ADSR (or a custom linearly interpolated envelope) plus optional edge fades to a folder of WAVs, writing new files and a before/after peak report. If attack+decay+release exceed the clip, the stages are scaled to fit. The input path is never overwritten (pass `--outdir` or `--suffix`).

## Usage

```bash
python3 sfx-envelope/sfx_envelope.py sfx/*.wav --outdir env/ --adsr 10,30,0.7,50 --json report.json
python3 sfx-envelope/sfx_envelope.py hit.wav --suffix _env --envelope 0:0,0.05:1,1:0
```

Run `python3 sfx-envelope/sfx_envelope.py --help` (or `gst sfx-envelope --help`) for every option. Requires Python 3.10+ with numpy (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). Complements audio-tidy, sfx-mix and wav-trim.

## Source and licence

Original code. PCM WAV only; other RIFF chunks are not copied. The envelope is a sample-accurate gain curve, not a DAW filter or compressor.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
