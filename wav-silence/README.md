# wav-silence

Write a silent PCM WAV, insert a silent gap into an existing WAV, or zero a time range (`--replace START,END`). Generated or inserted duration is `--duration` seconds. `smpl` loop markers are preserved (and shifted when silence is inserted before them). The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 wav-silence/wav_silence.py -o quiet.wav --duration 0.5 --rate 8000
python3 wav-silence/wav_silence.py take.wav -o out.wav --at 0.2 --duration 0.1
python3 wav-silence/wav_silence.py take.wav -o muted.wav --replace 0.1,0.3
```

Run `python3 wav-silence/wav_silence.py --help` (or `gst wav-silence --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only, via audio-tidy. Inserting without `--at` prepends the silence (at 0). Only the first smpl loop is rewritten. Other RIFF chunks are dropped on write. This is not a noise gate (it does not detect silence).

## Tests

`python3 -m pytest -q tests/test_batch28.py`
