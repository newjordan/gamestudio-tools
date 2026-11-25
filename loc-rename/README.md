# loc-rename

Rename keys in a localisation CSV. `--map` takes a JSON/CSV table or an inline `old=new,old=new` list; optional `--prefix` / `--suffix` are applied after the map. Colliding destination keys are refused unless `--prefer first|last`. Missing map keys are reported (and fail under `--strict`). The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 loc-rename/loc_rename.py strings.csv -o strings2.csv --map ui.hello=ui.hi,ui.bye=ui.farewell
python3 loc-rename/loc_rename.py strings.csv -o out.csv --prefix game.
```

Run `python3 loc-rename/loc_rename.py --help` (or `gst loc-rename --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only the key column is renamed; language cells are copied as-is. Duplicate source keys (kept as first-wins by loc-merge.load_csv) are reported in the JSON. A map entry whose old key is absent is listed, and is a non-zero exit only with `--strict`.

## Tests

`python3 -m pytest -q tests/test_batch26.py`
