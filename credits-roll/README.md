# credits-roll

Render a scrolling credits review GIF from a UTF-8 text file. Plain lines are body text; a line starting with `#` is a heading (larger); a blank line is a gap. The roll starts just below the frame and scrolls up at `--speed` pixels per second. Pillow's default font is used, or a TTF via `--font`.

## Usage

```bash
python3 credits-roll/credits_roll.py credits.txt -o credits.gif --width 320 --height 180 --speed 40 --font fonts/Game.ttf
```

Run `python3 credits-roll/credits_roll.py --help` (or `gst credits-roll --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). A review-link stand-in, not an in-engine credits sequence.

## Source and licence

Original code. Pillow metrics, no complex-script shaping. Palette GIF flattened onto `--bg`.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
