# atlas-rename

Rename frames in an atlas-pack / TexturePacker JSON with a regex (`--pattern` / `--replace`, backrefs allowed) or an explicit `old=new,old=new` map (or a JSON object). Colliding destination names are refused. The image is not rewritten. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 atlas-rename/atlas_rename.py hero.json -o hero2.json --map walk_01=idle_01,walk_02=idle_02
python3 atlas-rename/atlas_rename.py hero.json -o hero2.json --pattern 'walk_(\d+)' --replace 'hero_\1'
```

Run `python3 atlas-rename/atlas_rename.py --help` (or `gst atlas-rename --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

This rewrites frame names only, not the packed sheet. Array atlases update the `filename` (or `name`) field; hash atlases rename the object keys. `--pattern` uses Python `re.sub`. Unmentioned frames are kept as-is.

## Tests

`python3 -m pytest -q tests/test_batch28.py`
