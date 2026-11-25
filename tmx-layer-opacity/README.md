# tmx-layer-opacity

Set or report opacity and visibility on named Tiled layers (tile, object, image, group). `--list` prints the current values; `--set` / `--visible` write a new map. Duplicate layer names all receive the same assignment.

## Usage

```bash
python3 tmx-layer-opacity/tmx_layer_opacity.py map.json -o faded.json --set fog=0.4 --visible secrets=0
```

Run `python3 tmx-layer-opacity/tmx_layer_opacity.py --help` (or `gst tmx-layer-opacity --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Matching is by layer name only, not by path, so two layers with the same name are updated together. Image layer tint colour is not modified. `--list` without `-o` is report-only.

## Tests

`python3 -m pytest -q tests/test_batch22.py`
