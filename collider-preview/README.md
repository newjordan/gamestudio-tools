# collider-preview

See the collision shapes before the physics engine does: draw tile-colliders output (or a Tiled object layer) over the rendered map with translucent fills, outlines and optional index labels, with a report of shape count, covered area, overlapping pairs and shapes outside the map.

## Usage

```bash
python3 collider-preview/collider_preview.py colliders.json --map level.json --tileset tiles.png -o colliders.png --scale 2 --labels
python3 collider-preview/collider_preview.py colliders.json --size 1024x640 -o plain.png --fail-on-overlap
```

Run `python3 collider-preview/collider_preview.py --help` (or `gst collider-preview --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Takes tile-colliders output; renders maps through tile-preview.

## Source and licence

Original code on Pillow. Axis-aligned rectangles only (polygons and ellipses in Tiled object layers are not drawn).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
