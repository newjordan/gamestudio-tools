# dialogue-to-yarn

Rebuild a Yarn Spinner script from a dialogue-extract CSV (and an optional speaker-rename map). `#line:` ids, node titles, choice arrows and leftover tags are kept. Rows are grouped by node and written in CSV order. Speakers become `Name: text` prefixes. `--split` writes one `.yarn` per source file. The input CSV is never overwritten.

## Usage

```bash
python3 dialogue-to-yarn/dialogue_to_yarn.py loc.csv -o story.yarn --speakers map.json
python3 dialogue-to-yarn/dialogue_to_yarn.py loc.csv --split yarn/
```

Run `python3 dialogue-to-yarn/dialogue_to_yarn.py --help` (or `gst dialogue-to-yarn --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements dialogue-extract, vo-diff and voice-slate.

## Source and licence

Original code. The rebuild is a straight line/choice dump: it does not reconstruct `<<if>>` / jumps / inline expressions that dialogue-extract stripped.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
