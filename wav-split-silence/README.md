# wav-split-silence

Split a long WAV take at silences into numbered region files plus a cue list. Threshold, minimum silence, minimum keep, and pad (each region is expanded into neighbouring silence up to `--pad-ms`) are all configurable. 16/24/32-bit PCM out.

## Usage

```bash
python3 wav-split-silence/wav_split_silence.py session.wav -o takes/ --min-silence-ms 400 --min-keep-ms 200 --pad-ms 40 --json takes.json
```

Run `python3 wav-split-silence/wav_split_silence.py --help` (or `gst wav-split-silence --help`) for every option. Requires Python 3.10+ (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). Same job as Audacity's "Sound Finder" or `sox silence`, aimed at splitting a recorded reel into takes, not at sentence segmentation or VAD.

## Source and licence

Original code. Silence is a simple peak/RMS threshold on PCM samples, not a speech model. Other RIFF chunks (including `smpl` loops) are not copied onto the region files.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
