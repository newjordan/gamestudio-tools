# asset-unused

Report files in an asset folder that no Tiled map, atlas JSON, Godot scene/script or glTF file references. Sidecars (`.import`, `.uid`) of used files are not listed. Does not delete anything.

## Usage

```bash
python3 asset-unused/asset_unused.py ./assets --json unused.json --strict
```

Run `python3 asset-unused/asset_unused.py --help` (or `gst asset-unused --help`) for every option. Requires Python 3.10+.

Since 2.5.0 `project.godot` and `.cfg` files are read for `res://` references (main scene, icon, autoloads,
translations) instead of being listed as unused, and BMFont `.fnt` files (text or XML) reference their page images.
Paths built at run time (`"res://sfx/%s.wav" % name`) are still invisible; list them literally.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not parse Unity YAML, Unreal assets, or audio banks. A loc CSV is not treated as a source of file paths. GLB buffers are not unpacked for internal URIs. False positives are possible for files only referenced from code via string concatenation.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
