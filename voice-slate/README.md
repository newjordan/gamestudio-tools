# voice-slate

Build recording-session sheets per speaker from Yarn / ink scripts or a dialogue-extract CSV: lines in script order grouped by node, take ids and target file names, direction notes from tags, estimated read time and a session budget (takes x read time + per-line overhead) split into sessions at node boundaries. Writes per-speaker CSV, a printable slate.md and summary.json.

## Usage

```bash
python3 voice-slate/voice_slate.py scripts/*.yarn -o slate --takes 3 --session-min 120
python3 voice-slate/voice_slate.py lines.csv -o slate --speaker Ava --pattern 'vo/{speaker}/{id}.wav'
```

Run `python3 voice-slate/voice_slate.py --help` (or `gst voice-slate --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Built on dialogue-extract; vo-diff checks delivered files against the same ids.

## Source and licence

Original code. Parses Yarn Spinner and ink syntax through dialogue-extract (no third-party code). Read times use dialogue-extract's words-per-second guess; real actors vary.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
