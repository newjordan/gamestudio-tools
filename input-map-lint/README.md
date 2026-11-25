# input-map-lint

Lint an input map before players find the problems: actions with no bindings, one binding on two actions in a context, names differing only by case, bindings listed twice, plain keys shadowed by the same key plus a modifier, non-snake_case names, keyboard actions with no gamepad binding, and (with --scan) actions used in code but missing from the map or never referenced. Reads JSON maps or a Godot project.godot [input] section.

## Usage

```bash
python3 input-map-lint/input_map_lint.py project.godot --scan scripts/ --parity
python3 input-map-lint/input_map_lint.py inputs.json --allow confirm,jump --strict
```

Run `python3 input-map-lint/input_map_lint.py --help` (or `gst input-map-lint --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Reads Godot 4's text project.godot format on a best-effort basis (keys, mouse buttons, joypad buttons and axes, modifiers; only common special-key codes are named, others show as key#N). Code scanning is a regex over string literals and common Godot and Unity input calls, so dynamically built names are not seen.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
