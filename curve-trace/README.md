# curve-trace

Preview a curve-gen path (JSON samples, or control points via curve-gen) as a PNG, and optionally a GIF of a token travelling along it. Accepts a curve-gen JSON, a JSON list of points, a CSV, or `--points`. Draws the polyline, sample dots and an optional sprite. 2D only (z is ignored). The input is never overwritten.

## Usage

```bash
python3 curve-trace/curve_trace.py --points "0,0;4,2;8,0" -o path.png --gif path.gif --gif-frames 24
python3 curve-trace/curve_trace.py rail.json -o rail.png --sprite token.png
```

Run `python3 curve-trace/curve_trace.py --help` (or `gst curve-trace --help`) for every option. Requires Python 3.10+ with Pillow and numpy (uses curve-gen).

## Inspiration (catalogue entry)

None (new). Complements curve-gen.

## Source and licence

Original code. The preview is an orthographic 2D plot (Y is up on the page); it is not a perspective camera path or an engine gizmo. The GIF token does not rotate to the tangent unless you pre-rotate the sprite.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
