# dialogue-to-ink

Rebuild an ink script from a dialogue-extract CSV, keeping knot names (from the node column), `#line:` ids, choice stars and leftover tags. Speakers become `Name: text` prefixes. Optional `--speakers` map rewrites names. `--split` writes one `.ink` per source file. The input CSV is never overwritten.

## Usage

```bash
python3 dialogue-to-ink/dialogue_to_ink.py loc.csv -o story.ink --speakers map.json
python3 dialogue-to-ink/dialogue_to_ink.py loc.csv --split ink/
```

Run `python3 dialogue-to-ink/dialogue_to_ink.py --help` (or `gst dialogue-to-ink --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements dialogue-extract and dialogue-to-yarn.

## Source and licence

Original code. The rebuild is a straight line/choice dump: it does not reconstruct `if` / gathers / tunnels / diverts that dialogue-extract stripped.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
