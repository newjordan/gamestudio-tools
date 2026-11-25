# anim-rename

Rename clips in an anim-meta JSON with a regex (`--pattern` / `--replace`, backrefs allowed) or an explicit `old=new` map. Colliding destination names are refused.

## Usage

```bash
python3 anim-rename/anim_rename.py clips.json -o named.json --pattern '^hero_' --replace 'player_' --pretty
```

Run `python3 anim-rename/anim_rename.py --help` (or `gst anim-rename --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only top-level keys of the `clips` object are renamed; frame file names inside a clip are left alone (use asset-rename for those). `--map` wins when both a map entry and the regex match the same clip.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
