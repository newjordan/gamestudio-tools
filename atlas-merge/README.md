# atlas-merge

Merge two or more TexturePacker-style atlas JSON files (and their sheets) into one packed atlas. Frames are unpacked in memory and repacked with the same packer as atlas-pack. Colliding frame names are refused unless `--prefix` or `--prefer first`.

## Usage

```bash
python3 atlas-merge/atlas_merge.py hero.json fx.json -o packed/all --padding 1 --no-pot
```

Run `python3 atlas-merge/atlas_merge.py --help` (or `gst atlas-merge --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Rotated packed frames are refused. Frame names that only differ by path separators may flatten to the same temporary filename during the pack step (use --prefix). The packer is atlas-pack's MaxRects (not an optimal pack).

## Tests

`python3 -m pytest -q tests/test_batch30.py`
