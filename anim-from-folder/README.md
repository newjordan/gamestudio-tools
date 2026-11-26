# anim-from-folder

Build an anim-meta clips JSON from a folder of frames and a name pattern. `--pattern` uses `{clip}` and `{frame}` placeholders (for example `{clip}_{frame}.png`). Repeatable `--clip NAME=GLOB` gathers one named clip from a glob, sorted by the number in the filename. Frame names are written as stems (no extension) so they drop into atlas-to-godot, anim-hold and anim-rename.

## Usage

```bash
python3 anim-from-folder/anim_from_folder.py frames/ -o clips.json --pattern '{clip}_{frame}.png' --default-fps 12 --once die
```

Run `python3 anim-from-folder/anim_from_folder.py --help` (or `gst anim-from-folder --help`) for every option. Requires Python 3.10+.

Since 2.5.0 `--fps` and `--once` keys may be globs (`--fps 'walk-*=10'`, `--once 'idle*'`), exact clip
names win over globs, and both flags can be repeated (2.4.0 kept only the last one).

## Inspiration (catalogue entry)

None (new). Complements `anim-meta`, which groups frames with a fixed prefix-plus-number regex.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only files with `.png`, `.webp`, `.tga` or `.bmp` extensions are considered for `--pattern`. `{clip}` is non-greedy, so a name like `boss_walk_01.png` with `{clip}_{frame}.png` becomes clip `boss_walk`. Use `--clip` when the pattern is ambiguous. Numbering gaps are warned about, not repaired.

## Tests

`python3 -m pytest -q tests/test_batch23.py`
