# wav-loop-snap

Trim or pad a PCM WAV to a loop region taken from the file's `smpl` chunk (first loop) or from `--start` / `--end` (inclusive sample indices, smpl convention). If the region starts before 0 or ends past the last sample, silence is padded; then the file is sliced to `[start, end]` inclusive. A new `smpl` loop covering the whole output is written unless `--no-meta`.

## Usage

```bash
python3 wav-loop-snap/wav_loop_snap.py loop.wav -o snapped.wav
python3 wav-loop-snap/wav_loop_snap.py take.wav -o cut.wav --start 1000 --end 5000
```

Run `python3 wav-loop-snap/wav_loop_snap.py --help` (or `gst wav-loop-snap --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only the first `smpl` loop is used as the default region. `audio-tidy` re-encodes the PCM, so other RIFF chunks besides the new `smpl` are not preserved. This does not snap loop points to zero-crossings; it trims or pads to a given region.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
