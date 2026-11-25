# audio-convert

Batch WAV to OGG Vorbis / Opus / MP3 / FLAC with game presets (music, sfx, voice, mp3, flac) and optional loudness normalisation, through the local ffmpeg binary (list arguments, no shell).

## Usage

```bash
python3 audio-convert/audio_convert.py "audio/raw/*.wav" -o audio/ship --preset sfx --loudnorm -16
python3 audio-convert/audio_convert.py voice/*.wav -o voice/ship --preset voice --dry-run
```

Run `python3 audio-convert/audio_convert.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: audio pipeline helpers; follows audio-tidy and sfx-gen in the chain.

## Source and licence

Original wrapper code. Requires the `ffmpeg` binary (LGPL/GPL depending on build; it is not bundled or modified). It is a local file-to-file converter and launches no network or fleet work.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
