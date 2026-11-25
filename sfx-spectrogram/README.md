# sfx-spectrogram

Spectrogram PNG of a WAV with a waveform strip, plus a report of clipped ranges and silent ranges; linear or log frequency axis; optional CI failure on clipping.

## Usage

```bash
python3 sfx-spectrogram/sfx_spectrogram.py sfx/*.wav -o spectrograms/ --log --json report.json --fail-on-clip
```

Run `python3 sfx-spectrogram/sfx_spectrogram.py --help` (or `gst sfx-spectrogram --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with audio-tidy and sfx-gen.

## Source and licence

Original code (numpy FFT, Hann window). 0 dB is the loudest bin in the clip, so a full-scale sine reads about -6 dB.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
