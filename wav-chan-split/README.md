# wav-chan-split

Split a multi-channel WAV into mono stems (default names L/R, or 5.1 / 7.1, or `--names`) plus a cue/index JSON or CSV. `--join` interleaves mono stems back into one multi-channel WAV. Split and join move integer samples, so a same-width round trip is bit-exact. Inputs may be files or folders. The input path is never overwritten (pass `--outdir` or `--suffix`).

## Usage

```bash
python3 wav-chan-split/wav_chan_split.py bus.wav --outdir stems/ --json stems.json
python3 wav-chan-split/wav_chan_split.py stems/bus_L.wav stems/bus_R.wav --join stereo.wav
```

Run `python3 wav-chan-split/wav_chan_split.py --help` (or `gst wav-chan-split --help`) for every option. Requires Python 3.10+ with numpy (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). Complements wav-trim and audio-tidy.

## Source and licence

Original code. PCM WAV only; other RIFF chunks are not copied onto the output. Channel labels are conventional (L/R/C/LFE/Ls/Rs), not read from a WAVEFORMATEXTENSIBLE mask.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
