# loop-xfade

Make a WAV loop without a click: crossfade the last frames of the loop into the audio that precedes the loop start (equal-power or linear), keep the file's length and bit depth, write the smpl loop chunk, and report the wrap discontinuity before and after as a multiple of the typical sample step.

## Usage

```bash
python3 loop-xfade/loop_xfade.py music.wav -o music_loop.wav --start 44100 --end 441000 --fade-ms 80
python3 loop-xfade/loop_xfade.py music_with_smpl.wav -o out.wav --fade-frames 2000 --linear
```

Run `python3 loop-xfade/loop_xfade.py --help` (or `gst loop-xfade --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Take loop points from loop-finder or wav-loop-meta; wav-batch-meta then checks loudness.

## Source and licence

Original code. Standard loop crossfade technique. PCM WAV 16/24/32-bit only; other chunks (cue, list) are dropped. The fade eats into the last part of the loop, so the loop needs pre-roll audio before its start.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
