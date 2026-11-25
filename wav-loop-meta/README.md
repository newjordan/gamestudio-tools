# wav-loop-meta

Read, set and clear loop points in the RIFF `smpl` chunk of WAV files so engines loop the file natively; `from-json` applies loop-finder results in bulk. All other chunks are kept and RIFF sizes are fixed up. `set`, `clear` and `from-json` refuse to overwrite the input unless you pass `--in-place` (or a different `-o` / `--outdir`).

## Usage

```bash
python3 wav-loop-meta/wav_loop_meta.py show song.wav
python3 wav-loop-meta/wav_loop_meta.py set song.wav --start 1000 --end 20000 -o song_loop.wav
python3 wav-loop-meta/wav_loop_meta.py from-json loops.json --dir wavs/ -o looped/
```

Run `python3 wav-loop-meta/wav_loop_meta.py --help` (or `gst wav-loop-meta --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with loop-finder.

## Source and licence

Original code from the public RIFF/WAVE `smpl` chunk layout. loop-finder's exclusive `end` becomes the inclusive smpl end (end - 1). Whether your engine honours `smpl` loop points on import varies by engine and version; check in yours.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
