# cue-sheet

Build an audio cue list from a folder of WAV files, for FMOD / Wwise import reviews: duration, rate, channels, peak, RMS, LUFS, loop points from the smpl chunk, a loudness class (silent / oneshot / sfx / voice / music) and a suggested bus (from --rule path patterns, or the class). Writes CSV and JSON.

## Usage

```bash
python3 cue-sheet/cue_sheet.py audio/ --csv cues.csv --json cues.json
python3 cue-sheet/cue_sheet.py audio/ --rule 'vo/*=dialogue' --rule 'music/*=music'
```

Run `python3 cue-sheet/cue_sheet.py --help` (or `gst cue-sheet --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Loudness comes from wav-batch-meta; loop flags from wav-loop-meta. Feed the list to voice-slate or an engine importer.

## Source and licence

Original code. PCM WAV only. Class heuristics (folder names, duration, loop flag, channel count) are a starting point, not a substitute for a sound designer's bus list. LUFS figures are not a certified meter (see wav-batch-meta).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
