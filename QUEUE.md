# Build queue (48h push)

## Batch 1: done 24 Nov 2026. 12 tools
atlas-pack, sprite-slice, pixelize, normal-bake, terrain-noise, wfc-tiles, dungeon-gen,
sfx-gen, audio-tidy, asset-lint, gltf-inspect, dialogue-extract

## Batch 2: done. 8 tools
tile-extrude, palette-swap, sprite-fx, glb-lod, godot-import-presets, loop-finder, asset-viewer, fleet-jobs

## Batch 3: done. 8 tools
tilemap-convert, obj-to-glb, channel-pack, bmfont-gen, vo-diff, frames-to-sheet, palette-extract, asset-manifest

## Batch 4: done 24 Nov 2026. 9 tools
autotile-gen, pixel-lint, tile-colliders, mesh-colliders, uv-check, subtitle-timing, pseudoloc, audio-convert, build-report
(Dropped from the old queue: tiled-to-godot-tscn, because Godot's tile data is a binary-packed format that cannot be
verified without a Godot editor on the box. tile-colliders was added instead.)

## Batch 5: done 24 Nov 2026. 8 tools
image-diff, texture-seamless, tile-dedupe, atlas-convert, loc-check, sfx-variants, terrain-mesh, dialogue-graph

## Batch 6: done 24 Nov 2026. 9 tools
lut-tool, sprite-pivot, glb-diff, wav-loop-meta, tmx-to-json, game-data-lint, ldtk-to-csv, atlas-validate, font-check

## Batch 7: done 24 Nov 2026. 8 tools
normal-fix, anim-meta, terrain-erode, tex-gen, curve-gen, loc-convert, patch-pack, icon-gen

## Kit plumbing: done
`gst` (single CLI entry point), `install.sh` (+ requirements.txt, requirements-dev.txt, VERSION). Nothing installed anywhere.

## Batch 8: done 24 Nov 2026. 8 tools
ase-json-import, tileset-gen, heightmap-tools, sfx-spectrogram, dialogue-stats, team-outline (was "sprite-outline-batch"), obj-uv-unwrap, data-diff

## Batch 9: done 24 Nov 2026. 8 tools
tile-preview, sfx-bank, asset-rename, lit-preview, drop-sim, level-curve, font-subset, colorblind-sim

## Batch 10: done 24 Nov 2026. 8 tools
sprite-sheet-optimize, gif-to-frames, tileset-from-image, map-diff, mesh-pivot-fix, voice-slate, wav-batch-meta (reports LUFS per BS.1770, not a certified meter), input-map-lint
(Also fixed an old bug: audio-tidy's write_wav wrote 4-byte samples under a 3-byte header for 24-bit output; now tested.)

## Batch 11: done 24 Nov 2026. 8 tools
alpha-bleed (replaced the queued palette-quantize: pixelize already quantizes to a palette), sprite-shadow, map-reach, loc-fit, loop-xfade, sfx-mix, collider-preview, onion-skin

## Batch 12: done 24 Nov 2026. 8 tools
tilemap-stats, sprite-outline-gen, frame-timing-check, cue-sheet, level-budget, gltf-strip, text-wrap-bake, spritesheet-gif

## Batch 13: done 24 Nov 2026. 8 tools
hitbox-gen, audio-concat, wav-split-silence, map-clean, nine-slice, font-preview, parallax-preview, tile-anim-gif

## Batch 14: done 25 Nov 2026. 8 tools
wav-trim, tmx-layer-export, map-merge, loc-placeholder-lint, particle-preview, sprite-angles, material-audit, room-graph
(Also closed cheap gaps: encoded base64 zlib/gzip/csv tile data is decoded in tilemap-stats, map-clean, level-budget, map-diff, tile-preview and tile-anim-gif; zstd is still refused. External .tsx / .tsj tilesets are resolved in tile-anim-gif and tile-preview, and a .tsx file can be the tile-anim-gif input.)

## Batch 15: done 25 Nov 2026. 8 tools
wav-loud-apply, anim-retarget-fps, credits-roll, map-stamp, obj-weld, tmx-objects-csv, jump-arc, texture-resize

## Batch 16: done 25 Nov 2026. 8 tools
wav-chan-split, dialogue-to-yarn, tileset-wang, glb-rename-nodes, sheet-pad, sfx-envelope, map-reorder, gif-optimize
(Also closed cheap gaps: map-clean now packs firstgids and remaps GIDs unless --keep-firstgids; obj-weld keeps mtllib/usemtl/group/smoothing/comment lines; zstd tile data is decoded when Python 3.14+ compression.zstd, pyzstd, or zstd is importable — if none of those are installed, writing zstd is refused.)

## Batch 17: done 25 Nov 2026. 8 tools
map-crop, dialogue-to-ink, sprite-flip-sheet, tmx-props-lint, contact-sheet, curve-trace, godot-tileset, wav-gap-squeeze

## Batch 18: done 25 Nov 2026. 8 tools
tile-replace, atlas-to-godot, wav-dc-remove, map-layer-rename, prefab-index, obj-recenter,
anim-reverse, loc-missing
(Also a kit-wide consolidation: gst list --category / gst search / gst categories; consistent
--help, flags and exit codes; six documented pipelines in docs/pipelines/ with integration tests;
top-level CHANGELOG. Cut as 0.7.0.)

## Batch 19: done 25 Nov 2026. 8 tools
atlas-unpack, map-layer-merge, loc-plurals, obj-triangulate, anim-pingpong,
tmx-embed-tileset, cubemap-pack, nav-grid
(In-place overwrite policy: dest == input is refused unless `--in-place`. 139 of 150
then-existing tools gained the guard; generators and tools with a different consent
flag are exempt. Kit-wide tests in tests/test_overwrite.py.)

## Batch 20: done 25 Nov 2026. 8 tools
map-layer-split, ldtk-to-tiled, obj-transform, anim-splice, tmx-infinite-to-finite,
sfx-pitch, sprite-trim, glb-merge
Cut as 0.8.0 (166 tools). Also the kit-wide `--in-place` overwrite policy from the
same cut.

## Batch 21: done 25 Nov 2026. 8 tools
glb-split, loc-icu-extract, map-auto-layer, obj-normals, anim-hold, wav-fade,
sprite-stack, tmx-object-types
(`obj-triangulate` switched from a triangle fan to ear-clipping so concave n-gons
stay inside the polygon.)

## Batch 22: done 25 Nov 2026. 8 tools
loc-sort, map-fill, obj-bounds, anim-rename, wav-pad, sprite-canvas,
tmx-layer-opacity, map-rotate
Cut as 0.9.0 (182 tools).

## Batch 23: done 25 Nov 2026. 8 tools
sfx-reverse, loc-key-lint, map-mirror, obj-merge, anim-from-folder,
wav-loop-snap, tileset-merge, glb-uv-transform
Cut as 1.0.0 (190 tools). Official Godot 4.7.2.stable.official.ed1daf0bf loaded
the `.tres` / `.import` emitters; `godot-import-presets` `**` globs were fixed.

## Batch 24: done 25 Nov 2026. 8 tools
loc-merge, map-scale, obj-split, sfx-normalize, tileset-split, wav-chan-swap,
sprite-recolor, tmx-encode
Cut as 1.1.0 (198 tools). `godot-tileset` emits physics polygons, terrain sets and
compact-grid animations; `atlas-to-godot` unpacks rotated frames. Official Godot
4.7.2.stable.official.ed1daf0bf loaded all of those (`GODOT_BIN` test).

## Batch 25: done 25 Nov 2026. 8 tools
tmx-decode, loc-diff, map-chunk, obj-decimate, wav-resample, sprite-rotate,
tileset-renumber, glb-center
`sfx-normalize` gained `--lufs` / `--max-true-peak` (default remains sample-peak
dBFS). Cut with batch 26 as 1.3.0 (214 tools).

## Batch 26: done 25 Nov 2026. 8 tools
loc-rename, map-shift, obj-subdivide, wav-invert, sprite-scale, glb-weld,
tmx-world, wav-mono
Cut as 1.3.0 (214 tools).

## Batch 27: done 25 Nov 2026. 8 tools
loc-split, map-pad, obj-flip, wav-gain, sprite-pad, glb-quantize,
tmx-layer-filter, palette-apply
`sprite-rotate` / `sprite-scale` rewrite atlas JSON when given one.
`gst docs -o DIR` builds a static docs site. Cut as 1.4.0 (222 tools).

## Batch 28: done 25 Nov 2026. 8 tools
loc-join, map-blank, obj-validate, wav-silence, sprite-unpad,
glb-attr-drop, tmx-gid-usage, atlas-rename
Side-view Godot 4.7 platformer showcase at examples/showcase-platformer/
(jump-arc-validated gaps, one-way platforms, coin SFX, parallax, BMFont HUD).
`jump-arc --json` gained `end` and `out_of_bounds`. Cut as 1.5.0 (230 tools).

## Batch 29: done 25 Nov 2026. 8 tools
loc-stats, map-path, obj-clean-uv, wav-gate, sprite-reframe,
glb-attr-rename, tmx-anim-list, atlas-sort
HTML5 canvas showcase at examples/showcase-web/ (vanilla JS, no CDN, no npm;
Tiled JSON, atlas JSON, WAV and BMFont loaded by js/gst-loader.js; CutyCapt
first-frame preview). Cut as 1.6.0 (238 tools).

## Batch 30: done 25 Nov 2026. 8 tools
loc-fill, map-outline, obj-drop-unused, wav-limit, sprite-align,
glb-extras-strip, tmx-tileset-list, atlas-merge
Robustness pass: stdlib-only fuzz harness (tests/fuzz/) and `gst fuzz`
(--fast seeded subset in the normal suite; --long also mutates samples/).
Every reader tool exits 0, 1 or 2 with a one-line error (no traceback),
via lib/cli_error.py. Cut as 1.7.0 (246 tools).

## 1.8.0: done 25 Nov 2026. Input validation (no new batch)
GST_DEBUG=1, lib/gst_read.py GstInputError readers and decoder guards, fuzz classification and
a generic-wrapper-hit threshold. 246 tools, 333 tests. Cut as 1.8.0.


## Batch 31: done 25 Nov 2026. 8 tools
map-to-godot, loc-to-godot, ase-decode, asset-unused, dialogue-lint, godot-res-lint, texture-budget, anim-to-godot
Input-validation follow-through from 1.8.0: leftover generic-wrapper hits on the long set were fixed
(loop-finder, palette-swap, texture-resize, tile-extrude, gif-optimize, gif-to-frames, obj-to-glb, loc-check, pseudoloc),
and a fully-random-byte fuzz assertion was added so reader tools exit 1 or 2 on garbage (not 0).
Cut as 1.9.0 (254 tools).

## Batch 32: done 25 Nov 2026. 8 tools
map-objects-to-godot, hitbox-to-godot, tile-colliders-to-godot, nav-to-godot,
nine-slice-to-godot, font-to-godot, ase-to-godot, data-to-godot
Also: map-to-godot carries Tiled H/V/diagonal flips as TileSetAtlasSource
alternatives; loc-to-godot emits official .translation files via headless
Godot CSV import (or a Translation .tres fallback). Official long --debug
fuzz rerun on the final tree. Cut as 2.0.0 (262 tools).

## 2.1.0: done 25 Nov 2026. Gap closing in existing tools (no new batch)
map-objects-to-godot (Sprite2D with atlas region and flip flags for tile objects; isometric projection; verified by a
software-GL pixel comparison in official Godot 4.7.2), ase-to-godot (reverse / ping-pong / ping-pong-reverse tags and
repeat counts expanded), font-to-godot (binary BMFont v3 and XML; XML is converted because Godot 4.7.2 cannot read it),
nav-to-godot (solids from tile-colliders output: --colliders, or a sibling <map>.colliders.json by default),
and a pure-Python zstd decoder (lib/zstd_pure.py) wired into every tile-data reader. Cut as 2.1.0 (262 tools).

## 2.2.0: done 25 Nov 2026. Gap closing in existing tools (no new batch)
map-objects-to-godot (external .tsx and image-collection tilesets; animated tiles become AnimatedSprite2D with
SpriteFrames, verified by a software-GL pixel comparison and a resource read-back in official Godot 4.7.2),
ase-json-import (tag direction and repeat share lib/ase_tags.py with ase-to-godot; a two-frame ping-pong is now
seamless), font-to-godot (glyph rectangles checked against the real page image, typed error), nav-to-godot
(partial-cell collider overlap is cut rather than blocking the whole cell; --block-whole-cells restores 2.1.0),
and a real install.sh --venv run into a temp prefix (with --with-tests it also installs pytest). Cut as 2.2.0
(262 tools).

## 2.5.0: done 25 Nov 2026. Second sample game (top-down roguelite)
examples/sample-topdown (Ember Crypt): seeded dungeon-gen floors autotiled by
map-auto-layer with a tileset-gen blob sheet, a map-stamp boss arena, five enemy
kinds (chase/shoot/boss) on a generated navmesh, drop-sim loot, save/load with a
linted save file, en/de/fr text through the loc and font tools, keyboard and
gamepad input checked by input-map-lint, SFX and music from the sfx/wav tools.
86 gst tools (61 new to the samples). Imports in official Godot 4.7.2 with zero
errors; a seeded autoplay clears the run; a 73.6 s software-GL GIF/MP4 was
captured. Six kit bugs fixed with regression tests: dungeon-gen tileset,
atlas-to-godot trim margins, anim-from-folder fps globs, asset-unused
project.godot/.fnt references, nav-to-godot T-junction islands (platformer
level2_nav.tscn regenerated), and gst bundle shipping examples/*/work scratch.
Cut as 2.5.0 (262 tools).

## 2.4.0: done 25 Nov 2026. Complete sample game
examples/sample-game-full (Gem Runner): a playable action-platformer with 3
Tiled levels (flips, object layers, colliders, navmesh), Aseprite player and
enemy with tags and hitboxes, a nine-slice UI, a bitmap font, en/de
translations, a data-table enemy Resource, loop-point music, title and win
screens, and autoplay. Every asset comes from a gst command. It imports in
official Godot 4.7.2 with zero errors and autoplays to the win screen; a
24.9 s software-GL GIF/MP4 was captured. Two kit bugs found and fixed with
regression tests: godot-import-presets WAV loop modes, and the ase-to-godot
default res:// path. Cut as 2.4.0 (262 tools).

## 2.3.1: done 25 Nov 2026. MIT licence
Owner-chosen MIT licence (LICENSE, Copyright 2026 Jordan Newman / OmniSpace
Technologies LLC), README and per-tool Source and licence sections updated,
third-party attributions kept, box-specific paths removed. Cut as 2.3.1
(262 tools) after the licence changed bundled files.

## 2.3.0: done 25 Nov 2026. Gap closing in existing tools (no new batch)
map-objects-to-godot (staggered/hex maps keep Tiled's screen-pixel object
coordinates; tile_to_screen matches Tiled's stagger/hex grid; polylines become
Line2D plus a CollisionPolygon2D in segment mode, verified in official Godot
4.7.2), ase-json-import (rotated frames kept for atlas-to-godot; slices including
nine-slice insets and pivot written as Godot scene + StyleBoxTexture, canvas-space
PNG crops), nav-to-godot (cut pieces merged with neighbouring walkable
rectangles), and test_showcase_web_build_and_parse hardened (600s timeout, one
retry). Cut as 2.3.0 (262 tools).
