# glb-split

Split a multi-root or multi-mesh GLB / glTF into one pruned file per top-level scene node (default) or per mesh. Animations whose targets sit in the extracted subtree are kept; everything else is stripped with the same reachability pass as gltf-strip.

## Usage

```bash
python3 glb-split/glb_split.py hero.glb -o /tmp/parts --by node
```

Run `python3 glb-split/glb_split.py --help` (or `gst glb-split --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

External (non-data-URI) buffers and images are refused — convert to GLB first. Skinned meshes keep their joints in the node array; if a skin's skeleton root was not under the extracted node, some viewers may need a re-parent. Morph-target extras and custom extensions are not remapped.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
