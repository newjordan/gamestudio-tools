# asset-unused

Report files in an asset folder that no Tiled map, atlas JSON, Godot scene/script or glTF file references. Sidecars (`.import`, `.uid`) of used files are not listed. Does not delete anything.

## Usage

```bash
python3 asset-unused/asset_unused.py ./assets --json unused.json --strict
```

Run `python3 asset-unused/asset_unused.py --help` (or `gst asset-unused --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Does not parse Unity YAML, Unreal assets, or audio banks. A loc CSV is not treated as a source of file paths. GLB buffers are not unpacked for internal URIs. False positives are possible for files only referenced from code via string concatenation.

## Tests

`python3 -m pytest -q tests/test_batch31.py`
