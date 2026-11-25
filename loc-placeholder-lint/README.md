# loc-placeholder-lint

Check that placeholder tokens stay consistent across languages in a localisation CSV. Tokens: `{name}` and `{name:fmt}`, printf `%s %d %i %f %x` (`%%` is an escape, not a token), numbered printf `%1$s`, and `$var$`. Named placeholders are compared as a multiset; unnumbered printf tokens are compared in order. Missing translations are left to loc-check. JSON and text; exit 1 on any mismatch.

## Usage

```bash
python3 loc-placeholder-lint/loc_placeholder_lint.py loc/strings.csv --json ph.json
python3 loc-placeholder-lint/loc_placeholder_lint.py loc/strings.csv --source en --langs fr,de,ja
```

Run `python3 loc-placeholder-lint/loc_placeholder_lint.py --help` (or `gst loc-placeholder-lint --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements loc-check (which also looks at tags, escapes and length). This tool is the narrower, placeholder-only report.

## Source and licence

Original code. ICU plural / select messages are not parsed as a tree (a `{count, plural, ...}` block is treated as one named placeholder).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
