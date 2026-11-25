# HTML5 canvas showcase

A dependency-free top-down room at `examples/showcase-web/`. Vanilla JavaScript,
no CDN, no npm, and no Godot. Every runtime asset is produced by kit generators
and loaded directly: a Tiled JSON map, a TexturePacker-style atlas, a PCM WAV
and an AngelCode BMFont. The reusable loader is `js/gst-loader.js` (UMD, plus
`js/gst-loader.mjs` for ESM).

## Tools

tex-gen → pixelize → sprite-outline-gen → sprite-canvas → sprite-reframe →
sprite-shadow → atlas-pack → atlas-sort, plus map-blank → bake_room.py →
map-path, sfx-gen → sfx-normalize → wav-gate, bmfont-gen, and (for the preview)
frames-to-sheet → spritesheet-gif → gif-optimize.

## Rebuild

```bash
cd examples/showcase-web
./build_showcase.sh
```

The script wipes `art/`, `sfx/`, `font/` and `preview/`, then regenerates them.
Authored files (`index.html`, `js/`, `bake_room.py`, the README and the build
script) are left alone. `map-path` fails the build if the coin is not reachable
from spawn. When `cutycapt` and a display or `xvfb-run` are available, the
build serves the folder over HTTP and captures `preview/showcase.gif` and
`preview/shot_*.png`.

Serve the folder (`python3 -m http.server`) to play it: WASD or arrows walk,
collect the coin. `?preview=1` auto-walks; `?step=N` advances N fixed ticks
and stops. After the first successful frame the page sets `window.__GST_WEB_OK`.

`tests/test_showcase_web.py` copies the authored files, rebuilds without Godot,
parses every asset with the loader under Node, and screenshots the first frame
through the same CutyCapt / Xvfb path.

## Known gaps

Uncompressed base64 Tiled data is decoded; zlib / gzip / zstd layers are not.
Flipped Tiled GIDs are masked but not drawn with transforms. WAV is PCM only.
Opening `index.html` as `file://` may block asset fetches — use HTTP.
