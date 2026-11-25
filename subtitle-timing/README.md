# subtitle-timing

Build SRT, WebVTT and engine JSON subtitles from a dialogue CSV and the recorded WAVs (durations read from <id>.wav), wrapping to two lines, with reading-speed and length warnings.

## Usage

```bash
python3 subtitle-timing/subtitle_timing.py loc/lines_v2.csv --audio-dir vo/recordings -o subs/chapter1
# -> chapter1.srt, chapter1.vtt, chapter1.json (cues with start/end/lines)
```

Run `python3 subtitle-timing/subtitle_timing.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Yarn Spinner / ink localisation and VO workflows; takes dialogue-extract output.

## Source and licence

Original code (SRT and WebVTT formats are public specs).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
