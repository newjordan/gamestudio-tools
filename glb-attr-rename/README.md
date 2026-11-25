# glb-attr-rename

Rename vertex attributes on a static binary GLB (--map OLD=NEW or --pattern / --replace, backrefs allowed). POSITION cannot be renamed. Colliding destination names are refused. Accessors stay in place; the binary is not rebuilt.

## Usage

```bash
python3 glb-attr-rename/glb_attr_rename.py prop.glb -o prop2.glb --map TEXCOORD_0=TEXCOORD_1
```

Run `python3 glb-attr-rename/glb_attr_rename.py --help` (or `gst glb-attr-rename --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Binary .glb only. Animated, skinned or morphed files are refused. Names must match the glTF attribute keys exactly. The file is rewritten via glb-lod.save_glb (JSON + existing BIN chunk) so extras on the root are kept, but this is not a general glTF editor.

## Tests

`python3 -m pytest -q tests/test_batch29.py`
