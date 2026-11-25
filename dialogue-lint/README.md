# dialogue-lint

Validate Yarn Spinner and ink scripts for jumps or diverts to missing nodes, unmatched `[[` / `<<`, empty nodes, and (for Yarn) orphan nodes that nothing jumps to.

## Usage

```bash
python3 dialogue-lint/dialogue_lint.py story.yarn quest.ink --json lint.json
```

Run `python3 dialogue-lint/dialogue_lint.py --help` (or `gst dialogue-lint --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Public Yarn Spinner and inkle ink syntax.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not expand Yarn `<<if>>` / ink conditions, includes, or `-> END` variants beyond END/DONE/END_GAME. Stitch-relative ink diverts cover `-> name` and `-> knot.stitch` but not every divert shorthand. Orphan detection in Yarn treats the first node as the start.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
