# audio-tidy

Batch-clean WAVs: report peak/RMS, trim leading and trailing silence, normalise to peak or RMS dBFS, fade edges, downmix to mono, and resample. Reads 8/16/24/32-bit PCM.

## Usage

```bash
python3 audio-tidy/audio_tidy.py "vo/raw/*.wav"                       # report only
python3 audio-tidy/audio_tidy.py "vo/raw/*.wav" -o vo/clean --rms -18 --peak -1 --mono --rate 48000 --json vo/report.json
```

Run `python3 audio-tidy/audio_tidy.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: audio pipeline helpers (ffmpeg-normalize, sox scripts). Intended post-step for MiniMax Music / VO exports.

## Source and licence

Original code (Python stdlib `wave` + numpy). No third-party code.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
