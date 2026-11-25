# icon-gen

One master PNG to the whole app icon set: Windows `.ico`, macOS `.icns`, web favicons and maskable icon, Android mipmaps, Play Store and adaptive foreground, and iOS sizes flattened onto a background (no alpha).

## Usage

```bash
python3 icon-gen/icon_gen.py icon_1024.png -o icons/ --bg '#202830' --pad 8
```

Run `python3 icon-gen/icon_gen.py --help` (or `gst icon-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code using Pillow's ICO/ICNS writers. The size lists are the commonly used ones, not checked against current store rules; confirm the required sizes for your target at release time.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
