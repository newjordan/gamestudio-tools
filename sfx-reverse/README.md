# sfx-reverse

Reverse a PCM WAV in time (last sample becomes first). When the file has a RIFF `smpl` loop, the markers are remapped so they still cover the same audio after the reverse, unless `--no-remap-loops` is passed (the chunk is then dropped).

## Usage

```bash
python3 sfx-reverse/sfx_reverse.py whoosh.wav -o whoosh_rev.wav
```

Run `python3 sfx-reverse/sfx_reverse.py --help` (or `gst sfx-reverse --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only the first `smpl` loop is remapped (a second loop is reported and dropped). `audio-tidy` re-encodes the PCM, so other RIFF chunks besides the remapped `smpl` are not preserved. Reversing twice with remapped loops is identity for the PCM and the first loop.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
