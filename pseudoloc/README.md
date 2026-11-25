# pseudoloc

Pseudo-localise a strings CSV (accents, ~35% longer, bracketed) to find UI overflow, hard-coded text and encoding bugs before translations exist. Placeholders, tags and escapes are preserved.

## Usage

```bash
python3 pseudoloc/pseudoloc.py loc/strings.csv -o loc/strings_pseudo.csv --new-column pseudo
```

Run `python3 pseudoloc/pseudoloc.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: localisation workflow tools (pairs with loc-check and dialogue-extract).

## Source and licence

Original code (a standard localisation-testing technique).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
