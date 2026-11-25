# nine-slice-to-godot

Write a Godot 4 StyleBoxTexture `.tres` from an image and insets (`--insets L,T,R,B` or `--center X,Y,W,H`, same meaning as nine-slice). The PNG is referenced, not copied.

## Usage

```bash
python3 nine-slice-to-godot/nine_slice_to_godot.py panel.png -o panel_style.tres --insets 6,6,6,6 --res res://ui/
```

Run `python3 nine-slice-to-godot/nine-slice-to-godot.py --help` (or `gst nine-slice-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not write a Theme (only the StyleBox). Does not copy or reimport the PNG. Insets are pixels, not the baked 9-slice preview nine-slice writes.

## Tests

`python3 -m pytest -q tests/test_batch32.py`
