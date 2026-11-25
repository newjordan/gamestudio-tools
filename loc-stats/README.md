# loc-stats

Summarise a localisation CSV: key counts, per-language fill rates, character and word counts, longest strings, and duplicate keys. The CSV is not rewritten. Word counts are whitespace-separated tokens.

## Usage

```bash
python3 loc-stats/loc_stats.py strings.csv --json stats.json --csv langs.csv
```

Run `python3 loc-stats/loc_stats.py --help` (or `gst loc-stats --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

CSV only. Duplicate keys after the first are reported but not included in fill rates (first-wins). There is no ICU/plural awareness and no locale-specific word breaking (CJK strings without spaces count as one word).

## Tests

`python3 -m pytest -q tests/test_batch29.py`
