# loc-key-lint

Check loc-key naming conventions in a strings CSV (key column default `id`). Flags empty or whitespace keys, characters outside a charset, a missing prefix, leading/trailing or doubled separators, mixed separators, and duplicate keys. Exit 1 on findings unless `--no-fail`.

## Usage

```bash
python3 loc-key-lint/loc_key_lint.py strings.csv --prefix ui. --separator .
```

Run `python3 loc-key-lint/loc_key_lint.py --help` (or `gst loc-key-lint --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only (not PO / JSON dictionaries). The default charset is ASCII `A-Za-z0-9._-`; set `--charset` if you need other letters. `--separator` also flags `_`, `-` and `/` as mixed when the primary separator is `.`. The CSV is never rewritten.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
