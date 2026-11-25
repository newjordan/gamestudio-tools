# gif-to-frames

Split an animated GIF (or APNG / animated WebP, anything Pillow opens) into numbered, fully composited RGBA PNG frames with per-frame durations and loop count in frames.json; optionally merge identical consecutive frames or write a horizontal strip.

## Usage

```bash
python3 gif-to-frames/gif_to_frames.py reference.gif -o frames --strip
python3 gif-to-frames/gif_to_frames.py reference.gif -o frames --merge-same --prefix walk
```

Run `python3 gif-to-frames/gif_to_frames.py --help` (or `gst gif-to-frames --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). The reverse of the GIF preview in sprite-slice; feed the frames to frames-to-sheet or atlas-pack.

## Source and licence

Original code on Pillow (HPND licence). Frame compositing and disposal are Pillow's. Only reference animations you have the right to use should be imported.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
