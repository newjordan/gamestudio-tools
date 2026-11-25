# GST web showcase (HTML5 canvas)

A dependency-free top-down room in vanilla JavaScript. Every runtime asset —
tiles, Tiled JSON map, player atlas, coin WAV and BMFont HUD — is produced by
kit generators. There is no CDN, no npm, and no Godot in this project.

The reusable loader lives at `js/gst-loader.js` (UMD: a browser `<script>`,
`require`, or `import` via `js/gst-loader.mjs`). It parses Tiled JSON (array or
CSV; uncompressed base64), TexturePacker-style atlas JSON (hash or array),
AngelCode BMFont, and PCM WAV, and it draws those onto a canvas.

## Layout

A 20×10, 16 px-tile room (canvas 320×180, displayed at 2×) with a floor, a wall
ring, a 2×2 interior block, a spawn object and a coin. WASD or arrow keys walk;
collecting the coin plays the generated SFX and updates the BMFont HUD. A
`map-path` check during the build fails if the coin is not reachable.

Query flags used by the preview capture: `?preview=1` hides page chrome and
auto-walks toward the coin; `?step=N` advances N fixed 1/30 s ticks and stops;
`?muted=1` skips audio. After the first successful frame the page sets
`window.__GST_WEB_OK`.

Serve the folder over HTTP (for example `python3 -m http.server`). Opening
`index.html` as `file://` may block `fetch` of the assets.

## Rebuild

```bash
./build_showcase.sh
```

The script wipes `art/`, `sfx/`, `font/` and `preview/`, then regenerates them.
Authored files (`index.html`, `js/`, `bake_room.py`, this README, the build
script) are left alone. When `cutycapt` and a display or `xvfb-run` are
available, it also writes `preview/showcase.gif`, `preview/shot_*.png` and
`preview/sheet.png`.

## Verify

```bash
python3 -m http.server 8765 --bind 127.0.0.1
# in another shell, or via the kit test:
node js/parse-check.mjs .
```

`tests/test_showcase_web.py` copies the authored files, rebuilds without Godot,
parses every asset with the loader under Node, and (when CutyCapt / Xvfb is
present) screenshots the first frame of the served page.

## Known gaps

Uncompressed base64 Tiled data is decoded; zlib / gzip / zstd layers are not.
Flipped Tiled GIDs are masked but not drawn with transforms. WAV is PCM only.
The loader does not implement a general audio graph or a tile-animation clock
(`tmx-anim-list` / `tile-anim-gif` cover that on the kit side).
