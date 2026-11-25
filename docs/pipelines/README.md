# End-to-end pipelines

Documented chains of kit tools. Each one has a markdown file here and an integration test in
`tests/test_pipelines.py`. The tests build their own fixtures (the release tarball does not include
`samples/`), so `gst test` is enough after a `--with-tests` install.

If you have the source tree, the same chains can be run against `samples/pipelines/` from the kit
root (examples below use `/tmp/pipe-*` for outputs so nothing is overwritten).

| Pipeline | Tools | Doc |
|---|---|---|
| Sprite art to padded atlas to Godot | palette-apply, sprite-recolor, sprite-rotate, sprite-scale, sprite-pad, sprite-unpad, sprite-reframe, sprite-align, sprite-stack, sprite-canvas, anim-from-folder, atlas-pack, atlas-merge, atlas-rename, atlas-sort, atlas-unpack (round-trip), sheet-pad, atlas-to-godot | [sprite-to-godot.md](sprite-to-godot.md) |
| Tiled map lint, clean, crop, stats | tmx-props-lint, tmx-object-types, map-clean, map-crop, tilemap-stats, map-layer-merge, map-auto-layer, map-fill, tmx-layer-opacity, map-rotate, map-mirror, map-scale, tmx-decode, map-shift, map-pad, map-blank, map-chunk, tmx-world, tileset-renumber, tmx-layer-filter, tmx-gid-usage, tmx-anim-list, tmx-tileset-list, map-path, map-outline, tmx-encode, nav-grid | [tiled-map-hygiene.md](tiled-map-hygiene.md) |
| VO script to slate to trim to loudness | dialogue-extract, voice-slate, wav-dc-remove, wav-trim, wav-silence, wav-gate, wav-limit, wav-resample, wav-mono, wav-invert, wav-gain, wav-loud-apply, sfx-normalize (--lufs), wav-chan-swap, wav-fade, wav-pad, sfx-reverse, wav-loop-snap | [vo-slate-to-loudness.md](vo-slate-to-loudness.md) |
| glTF strip, rename, pivot, material audit | obj-split, obj-merge, obj-triangulate, obj-subdivide, obj-decimate, obj-drop-unused, obj-flip, obj-validate, obj-clean-uv, obj-normals, obj-bounds, obj-to-glb, gltf-strip, glb-extras-strip, glb-weld, glb-quantize, glb-attr-drop, glb-attr-rename, glb-rename-nodes, mesh-pivot-fix, glb-center, glb-uv-transform, material-audit, glb-split | [gltf-cleanup.md](gltf-cleanup.md) |
| Loc missing, placeholders, check, plurals | loc-merge, loc-rename, loc-split, loc-join, loc-stats, loc-diff, loc-fill, loc-missing, loc-placeholder-lint, loc-check, loc-plurals, loc-icu-extract, loc-sort, loc-key-lint | [loc-pass.md](loc-pass.md) |
| Tileset generate, wang, Godot | tileset-gen, tileset-wang, tileset-merge, tileset-split, godot-tileset | [tileset-to-godot.md](tileset-to-godot.md) |
| Godot 4.7 showcases (all kit-generated assets) | tex-gen, map-blank, jump-arc, godot-tileset, sprite tools, atlas-to-godot, sfx-gen, parallax-preview, bmfont-gen, godot-import-presets, frames-to-sheet, spritesheet-gif, gif-optimize | [godot-showcase.md](godot-showcase.md) |
| HTML5 canvas showcase (vanilla JS, no CDN) | tex-gen, map-blank, map-path, sprite tools, sprite-reframe, atlas-pack, atlas-sort, sfx-gen, wav-gate, bmfont-gen, frames-to-sheet, spritesheet-gif, gif-optimize | [web-showcase.md](web-showcase.md) |

Exit codes are the kit convention: 0 success, 1 issues / CI fail, 2 usage error. Commands below use
`gst` (or `python3 <tool>/<tool_with_underscores>.py` if you prefer).
