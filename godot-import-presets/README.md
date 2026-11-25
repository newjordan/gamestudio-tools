# godot-import-presets

Bulk-write Godot 4 `.import` files from glob rules (pixel, ui, albedo3d, normal3d, wav-loop, wav-oneshot) and print nearest-filter project.godot defaults.

## Usage

```bash
python3 godot-import-presets/godot_import_presets.py game/ -r import_rules.json --dry-run
python3 godot-import-presets/godot_import_presets.py --project-snippet
# import_rules.json: {"rules":[{"glob":"art/sprites/**/*.png","preset":"pixel"},{"glob":"audio/music/*.wav","preset":"wav-loop"}]}
```

WAV presets (2.4.0): `wav-loop` imports a WAV that carries a `smpl` loop (from `wav-loop-meta` / `loop-finder`) with loop mode *Detect From WAV*, so Godot uses the embedded loop points; a WAV without one loops whole-file *Forward*. `wav-oneshot` is *Disabled*, so a stray `smpl` chunk never makes a one-shot loop. A rule's `params` can still set `edit/loop_mode` explicitly.

Run `python3 godot-import-presets/godot_import_presets.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: Godot-side tooling and engine-integration entries (Terrain3D, Godot import pipeline).

## Source and licence

Original code following the Godot 4 `.import` text layout. Verified in official Godot 4.7.2.stable.official.ed1daf0bf (the editor fills in `uid` / dest paths). `**` globs are path-style (`art/**/*.png` matches files in `art/` as well as in subfolders). Try one folder with --dry-run first. The optional kit test `tests/test_godot_load.py` runs when `GODOT_BIN` is set.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
