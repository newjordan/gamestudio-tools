# dialogue-graph

Map Yarn and ink dialogue flow: nodes and jumps, missing targets, nodes unreachable from the start, and ink dead ends, with Graphviz DOT and Mermaid export.

## Usage

```bash
python3 dialogue-graph/dialogue_graph.py story/*.yarn --dot story.dot --mermaid story.mmd --json story.json
python3 dialogue-graph/dialogue_graph.py story/main.ink --strict
```

Run `python3 dialogue-graph/dialogue_graph.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Yarn Spinner and ink (narrative authoring).

## Source and licence

Original code from the public Yarn and ink syntax docs; no code from either project. The ink parser covers knots, stitches and `->` diverts, not every ink feature (tunnels, threads and functions are not followed).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
