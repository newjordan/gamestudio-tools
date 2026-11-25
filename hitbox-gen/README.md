# hitbox-gen

Collision shapes (AABB, circle, and a vertical or horizontal capsule) from sprite alpha. Works on loose frames, a `--grid` sheet, or an atlas JSON (trimmed frames are reconstructed onto `sourceSize` so the box is in sheet/source space). Optional padding, centroid-based circles, and normalized 0–1 coordinates.

## Usage

```bash
python3 hitbox-gen/hitbox_gen.py sprites/ -o hitboxes.json --pad 1
python3 hitbox-gen/hitbox_gen.py --atlas atlas.json -o hitboxes.json --normalized --centroid
python3 hitbox-gen/hitbox_gen.py sheet.png --grid 16x16 -o hitboxes.json
```

Run `python3 hitbox-gen/hitbox_gen.py --help` (or `gst hitbox-gen --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Complements tile-colliders (tile solid masks) and collider-preview (drawing boxes onto a map). The circle is the AABB centre, or the alpha centroid with `--centroid`; it is not a smallest enclosing circle.

## Source and licence

Original code. Atlas reconstruction follows the same `spriteSourceSize` / `sourceSize` convention used by sprite-slice and spritesheet-gif.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
