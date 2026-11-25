# dialogue-extract

Extract spoken lines from Yarn Spinner (.yarn) and ink (.ink) scripts into a VO/localisation CSV: stable ids (keeps #line: tags, can write generated ones back), speaker, node/knot, tags, word count, and estimated VO seconds.

## Usage

```bash
python3 dialogue-extract/dialogue_extract.py "story/**/*.yarn" "story/*.ink" -o loc/lines.csv
python3 dialogue-extract/dialogue_extract.py story/*.yarn --speaker Ava -o vo/ava_script.csv
python3 dialogue-extract/dialogue_extract.py story/*.yarn --tag-in-place -o loc/lines.csv  # stamps #line: ids
```

Run `python3 dialogue-extract/dialogue_extract.py --help` for every option. Requires Python 3.10+ with Pillow and numpy (gltf-inspect needs only the stdlib; Pillow is optional for texture sizes).

## Inspiration (catalogue entry)

Catalogue: Yarn Spinner (MIT), inkle ink (MIT), localisation/VO pipeline tools.

## Source and licence

Original code following the public Yarn and ink syntax docs. No code from Yarn Spinner or ink.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
