# dialogue-stats

Statistics for Yarn and ink scripts: lines, words, VO minutes, per-speaker share, narration share, missing line ids, longest lines, branching factor and terminal nodes; flags lines over a word limit.

## Usage

```bash
python3 dialogue-stats/dialogue_stats.py story/*.yarn story/*.ink --max-words 40 --md stats.md --json stats.json
```

Run `python3 dialogue-stats/dialogue_stats.py --help` (or `gst dialogue-stats --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Yarn Spinner and ink (narrative authoring).

## Source and licence

Original code built on this kit's dialogue-extract and dialogue-graph parsers, so their syntax limits apply (the ink parser skips tunnels, threads and functions).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
