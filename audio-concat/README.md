# audio-concat

Concatenate WAV files into one reel: optional silence gaps, an optional slate beep before each clip, resample and channel match, a peak ceiling, and a cue list in CSV and/or JSON (start, end, duration, source path). `--peak-db` (default -1) only turns the reel down when it is louder than that ceiling; a quieter reel is not turned up. When nothing is resampled, folded, slated, or scaled, the PCM samples are copied as integers (a same-width reel is bit-exact, including exact silence for `--gap-ms`). 16/24/32-bit PCM out.

## Usage

```bash
python3 audio-concat/audio_concat.py vo/*.wav -o session.wav --gap-ms 200 --slate-ms 80 --cues-json session.cues.json
python3 audio-concat/audio_concat.py a.wav b.wav -o reel.wav --rate 48000 --channels 2 --peak-db -1
```

Run `python3 audio-concat/audio_concat.py --help` (or `gst audio-concat --help`) for every option. Requires Python 3.10+ (uses audio-tidy for WAV I/O).

## Inspiration (catalogue entry)

None (new). A small stand-in for `sox` concatenate / DAW assembly, so review reels can be built on the box without an extra package.

## Source and licence

Original code. Reads and writes PCM WAV via audio-tidy's helpers (including the 24-bit 3-byte sample path). Other RIFF chunks are not preserved in the output reel.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
