# sfx-bank

Pack many short WAVs into one audio-sprite WAV with an index (frames and seconds), optional Howler.js sprite map, resampling and channel matching, and unpack to get the clips back.

## Usage

```bash
python3 sfx-bank/sfx_bank.py pack sfx/ -o ui_bank --mono --gap 0.05 --howler
python3 sfx-bank/sfx_bank.py unpack ui_bank.wav ui_bank.json -o clips/
```

Run `python3 sfx-bank/sfx_bank.py --help` (or `gst sfx-bank --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Pairs with audio-convert for encoding the bank.

## Source and licence

Original code. Lossless 16-bit PCM; the Howler map has no loop flags (add them by hand). Keep the gap larger than your encoder delay.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
