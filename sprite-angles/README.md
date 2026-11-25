# sprite-angles

Bake a sprite at N rotation angles (8-dir / 16-dir, or any `--angles` count) as a sheet plus atlas JSON. Angle 0 is the original orientation; further frames rotate clockwise in equal steps (`--ccw` to go the other way). Each frame is drawn onto a canvas large enough for the diagonal so nothing is clipped. Nearest-neighbour by default. The atlas JSON follows the same frame / spriteSourceSize / sourceSize layout as atlas-pack.

## Usage

```bash
python3 sprite-angles/sprite_angles.py hero.png -o hero_8.png --angles 8
python3 sprite-angles/sprite_angles.py ship.png -o ship_16.png --angles 16 --ccw --pivot feet
```

Run `python3 sprite-angles/sprite_angles.py --help` (or `gst sprite-angles --help`) for every option. Requires Python 3.10+ with Pillow.

## Inspiration (catalogue entry)

None (new). A pre-rotation sheet for 8-dir / 16-dir games, not a runtime rotator.

## Source and licence

Original code. Nearest-neighbour rotation of pixel art will look jaggy at odd angles; that is expected.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
