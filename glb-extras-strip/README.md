# glb-extras-strip

Remove every `extras` object from a glTF JSON document (binary .glb or .gltf). The binary buffer is left in place; the file is not rebuilt beyond rewriting the JSON chunk. Animated, skinned and morphed files are allowed.

## Usage

```bash
python3 glb-extras-strip/glb_extras_strip.py prop.glb -o prop_clean.glb
```

Run `python3 glb-extras-strip/glb_extras_strip.py --help` (or `gst glb-extras-strip --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Only the extras key is removed (including nested extras). Custom extensions are kept. A .glb is rewritten via glb-lod.save_glb (JSON plus the existing BIN chunk).

## Tests

`python3 -m pytest -q tests/test_batch30.py`
