# godot-res-lint

Check Godot 4 `.tscn`, `.tres` and `.gd` files for `res://` paths that do not resolve under the project root. Optional `--uid` warns when a referenced file has no `.uid` sidecar.

## Usage

```bash
python3 godot-res-lint/godot_res_lint.py ./game --json missing.json
```

Run `python3 godot-res-lint/godot_res_lint.py --help` (or `gst godot-res-lint --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not execute GDScript, so paths built with string concatenation are missed. Does not validate `uid://` identifiers against `uid_cache.bin`. Shader `hint` paths and `.import` remaps are not followed.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
