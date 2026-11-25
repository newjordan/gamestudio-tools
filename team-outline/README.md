# team-outline

Team-colour variants of sprites: recolour the outline (edge pixels or a named outline colour) and/or a hue-keyed area (for example magenta cloth) with shading preserved, one PNG per sprite and team.

## Usage

```bash
python3 team-outline/team_outline.py units/*.png -o teams/ --team red='#e03030' --team blue='#3060e0' --edge --key '#ff00ff'
```

Run `python3 team-outline/team_outline.py --help` (or `gst team-outline --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Pixelorama and LibreSprite (pixel-art tooling).

## Source and licence

Original code. Alpha is never modified. Anti-aliased art may need a larger --tol or --hue-tol.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
