# Changelog

All notable changes to gamestudio-tools are recorded here. The kit is versioned
with a `VERSION` file and a reproducible `gst bundle` tarball.

## 2.5.0 — 2026-11-25

Adds a second complete sample game, a top-down roguelite that exercises 61 tools
the platformer did not touch, and fixes six kit bugs (five exposed by the game, one
in `gst bundle`). No new tools (262).

### Added

- `examples/sample-topdown/`: *Ember Crypt*, a top-down action roguelite for
  Godot 4.7. Two procedurally generated floors (`dungeon-gen` BSP, seeded from
  the run seed) autotiled by `map-auto-layer` with a 47-tile blob sheet from
  `tileset-gen`, plus a boss arena built with `map-blank`, `map-fill` and
  `map-stamp`. Five enemy kinds with chase, shoot and boss behaviours on a
  generated NavigationRegion2D, pickups rolled from `drop-sim`-checked loot
  tables, a HUD (nine-slice panel, atlas-unpacked icons, BMFont labels),
  save/load between floors (the written save is linted by `game-data-lint`),
  en/de/fr text through `loc-check`, `loc-key-lint`, `loc-placeholder-lint`,
  `loc-fit`, `pseudoloc`, `font-subset`, `bmfont-gen` and `loc-to-godot`,
  keyboard plus gamepad on every action (`input-map-lint --parity --strict`),
  12 SFX from `sfx-gen`/`sfx-pitch`/`sfx-variants`/`sfx-envelope`/`sfx-reverse`/
  `sfx-mix` and a 16 s music loop mixed by `sfx-mix`, levelled by
  `wav-loud-apply` and cut by `wav-loop-snap`. `build.sh` runs 86 gst tools and
  the README maps every generated file to its command. A seeded autoplay run
  clears both floors and the boss identically every time; `build.sh --movie`
  records a 73.6 s software-GL `--write-movie` capture to `media/gameplay.gif`
  and `media/gameplay.mp4`.
- `tests/test_v25.py`: eight regression tests for the bugs below (all fail on
  2.4.0 code; three load the result in Godot when `GODOT_BIN` is set) and three
  sample tests: the README maps every generated asset and tool, the asset build
  is reproducible byte for byte, and (with `GODOT_BIN`) the project imports with
  zero errors and the autoplay clears the run in two locales with identical
  gameplay.

### Fixed

- `dungeon-gen`: the JSON map had an empty tileset, so `map-to-godot` drew no
  cells and `map-reach`/`nav-to-godot` saw an all-walkable map. It now embeds a
  two-tile tileset (`<out>_tiles.png`, wall tile `solid=true`), layer ids,
  `nextlayerid`/`nextobjectid`, and in BSP mode a `rooms` object layer; new
  `--tile`.
- `atlas-to-godot`: trimmed atlas-pack frames lost their offset and original
  canvas (animations jittered and pivots moved). AtlasTextures now get
  `margin` from `spriteSourceSize`/`sourceSize`; verified in Godot 4.7.2 (a
  6x4 trimmed frame reports 16x16).
- `anim-from-folder`: `--fps` matched exact clip names only and a repeated
  `--fps` silently replaced the earlier one. Keys may now be globs, exact names
  win, and `--fps`/`--once` are repeatable.
- `asset-unused`: `project.godot` was listed as unused and its references
  (icon, main scene, autoloads, translations) were ignored, as were BMFont
  page images. Both are now read.
- `nav-to-godot`: each rectangle had private vertices, and Godot links
  navigation polygons only across identical edges, so rooms meeting a corridor
  at a T-junction were islands and `map_get_path` returned nothing. Vertices
  are welded and T-junctions split; verified with a Godot path query.
  `examples/sample-game-full/project/levels/level2_nav.tscn` is regenerated
  with the fix (two platforms now share edges); the platformer autoplay still
  wins in 22.3 s.
- `gst bundle`: it walked `examples/<game>/work/`, the gitignored scratch that
  `build.sh` leaves behind, so a bundle cut after `build.sh --movie` grew from
  about 8 MB to 45 MB (a 43 MB movie AVI and raw WAVs). Those folders are now
  skipped; a `work` folder anywhere else is still shipped.

## 2.4.0 — 2026-11-25

Adds a complete sample game and fixes two kit bugs it exposed. No new tools (262).

### Added

- `examples/sample-game-full/`: *Gem Runner*, a playable 2D action-platformer
  for Godot 4.7. It has three Tiled levels with flipped tiles (H, V and
  diagonal), object layers, merged colliders, one-way platforms and a
  NavigationRegion2D. Its Aseprite player and slime have tagged animations
  and per-frame hitboxes. It also has a nine-slice UI, a bitmap font, en/de
  translations, a data-table enemy stats Resource, looping music with
  embedded loop points, generated SFX, a title screen, a win screen and an
  autoplay test driver. `build.sh` produces every asset with gst; its
  README maps each asset to the command that made it. `build.sh --movie`
  records a 24.9 s software-GL `--write-movie` capture to
  `media/gameplay.gif` and `media/gameplay.mp4`.
- `tests/test_v24.py`: two regression tests for the bugs below, plus three
  sample-game tests. They check that the README maps every generated asset,
  that the asset build is reproducible byte for byte, and (with
  `GODOT_BIN`) that the project imports with zero errors and autoplays
  through level 3 to the win screen in both locales.

### Fixed

- `godot-import-presets`: the `wav-loop` preset forced loop mode *Forward*
  over the whole file, so Godot ignored the `smpl` loop points that
  `wav-loop-meta` and `loop-finder` write. `wav-oneshot` used *Detect*, so a
  one-shot WAV with a `smpl` chunk would loop. Now `wav-loop` uses *Detect*
  when the WAV carries a `smpl` loop (else whole-file *Forward*), and
  `wav-oneshot` uses *Disabled*. Verified in official Godot 4.7.2
  (`loop_begin`/`loop_end` read back from the import).
- `ase-to-godot`: without `--res`, frame textures were referenced as
  `res://frame_NNNN.png`, although the PNGs are written to `<out>_frames/`.
  The default is now derived from the nearest `project.godot` above the
  frames folder. With no project above it, `res://<frames folder>/` is
  used and a note is printed.

## 2.3.1 — 2026-11-25

Applies the MIT licence chosen by the owner. No new tools (262).

### Changed

- Added `LICENSE` (MIT, Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).
  The root README licence section and every tool's **Source and licence**
  section now state MIT. Third-party attributions (sfxr, glTF-Transform,
  Machado et al. colour matrices, Pillow, DejaVu/Bitstream Vera, and others
  already credited in those READMEs) are unchanged.
- Replaced box-specific paths (`/workspace/gamestudio-tools`,
  `/workspace/godot-official`, `/home/box`, and similar) with repo-relative
  or generic wording so the tree can be cloned anywhere.
- `tests/test_batch13.py` no longer depends on `samples/` or an absolute
  box path: the font-preview case uses `tests/fixtures/DejaVuSans-subset.ttf`
  (DejaVu / Bitstream Vera licence in the same folder).

### Tests

- Official long fuzz (seed 1): 4060 cases, 0 generic hits, 0 timeouts, 0
  signals, 0 bad exits, 0 accepted-garbage.

## 2.3.0 — 2026-11-25

Closes more remaining gaps in existing tools. No new tools (262).

### Changed

- `map-objects-to-godot`: staggered and hexagonal maps keep the object
  coordinates Tiled stores (already screen pixels — Tiled's hexagonal
  renderer inherits the orthogonal identity for pixel-to-screen). Applying
  the diamond isometric formula would put objects in the wrong place.
  `Projection.tile_to_screen` maps *tile* coordinates the same way Tiled
  does, honouring `staggeraxis`, `staggerindex` and `hexsidelength`, and
  those fields are stored as metadata on the scene root. Polylines become
  a `Line2D` (`closed = false`, width from `--line-width`, default 2) plus
  a `CollisionPolygon2D` with `build_mode = 1` (segments — Godot has no
  dedicated polyline collider). Verified in official Godot 4.7.2: a
  script read-back of Line2D points, `closed`, width and `build_mode`,
  and a software-GL render of a staggered tile object at its pixel
  coordinates.
- `ase-json-import`: rotated frames are kept in the atlas JSON
  (`rotated: true`) so `atlas-to-godot` can unpack them. Slices,
  including nine-slice `center` insets and `pivot`, are written as
  `<out>.slices.json` and `<out>.slices.tscn` (each slice is a `Node2D`
  with `metadata/bounds`, `metadata/pivot`, `metadata/insets`, and a
  `Sprite2D` whose `offset` is `-pivot`). Nine-slice slices also get a
  `StyleBoxTexture` `.tres`. When the sheet is available (`--sheet` or
  `meta.image` next to the JSON), each slice is cropped in canvas space
  (rotated frames are un-packed first) so the Godot resources point at a
  usable PNG, not a packed/rotated atlas rect. A non-string `meta.image`
  is ignored rather than raising a raw `TypeError`. Verified in official
  Godot 4.7.2 (StyleBoxTexture margins, sprite offset and texture size).
- `nav-to-godot`: cut pieces are merged with neighbouring walkable
  rectangles that share a full edge (`merge_rects`), so a half-tile wall
  does not leave a strip of small leftover polygons. Coverage is
  unchanged (the same union, still a partition). If there are more than
  2048 distinct edges the merge is skipped and `--json` records
  `merged: false`. The 2.2.0 property test and a Godot 4.7.2 load still
  pass; a mid-column wall that used to emit 7 outlines now emits 3.
- `test_showcase_web_build_and_parse`: timeout raised from 180s to 600s
  (`GST_SHOWCASE_BUILD_TIMEOUT` overrides) and the build is retried once
  from a clean copy on `TimeoutExpired`, so a load spike on a ~30s build
  does not fail the suite.

### Tests

- `tests/test_v23.py`: stagger/hex `tile_to_screen` (including staggeraxis
  x/y, odd/even, and hexagonal hexsidelength), polyline Line2D emission
  (orthogonal and isometric), Godot 4.7.2 read-back and a staggered
  sprite render, rotated-frame unpack plus slice/nine-slice/pivot Godot
  load, and nav neighbouring-cell merge (including an L-shape unit test).
- Official long fuzz (seed 1): 4060 cases, 0 generic hits, 0 timeouts, 0
  signals, 0 bad exits, 0 accepted-garbage.

## 2.2.0 — 2026-11-25

Closes more remaining gaps in existing tools. No new tools (262).

### Changed

- `map-objects-to-godot`: external `.tsx` tilesets are parsed, including
  image-collection tilesets (per-tile `<image>`, relative paths resolved
  next to the `.tsx`) and `<tileoffset>`. Animated tiles become an
  `AnimatedSprite2D` whose `SpriteFrames` is built from `AtlasTexture`
  frames (one shared resource per animated tile, durations scaled to the
  greatest common divisor, `autoplay = "default"`, looping);
  `--no-animation` keeps a plain `Sprite2D` of the first frame. Verified
  in official Godot 4.7.2: a software-GL render of the first frame, a
  diagonally flipped animated tile and collection-tile images matches a
  Pillow reference, and a script read-back confirms frame count, speed,
  durations and autoplay. `map_diff.load_tsx` now also reads `tileoffset`
  and per-tile images; a bad number in an external tileset is a typed
  error.
- `ase-json-import`: tag directions (forward, reverse, pingpong,
  pingpong_reverse) and Aseprite `repeat` counts use the same expansion
  as `ase-to-godot`, factored into `lib/ase_tags.py`. A tag with
  `repeat` N plays N cycles and does not loop; other tags loop unless
  named in `--once`; `--ignore-direction` plays every tag forward and
  forever. A two-frame ping-pong is now `a, b` (it was `a, b, a`), so a
  looping clip is seamless. Malformed exports give a typed
  `GstInputError`.
- `font-to-godot`: every glyph rectangle is checked against the real
  size of its page image (text, XML and binary). A negative rectangle,
  one that passes the page edge (touching it is fine), or a glyph on an
  undeclared page is refused with `BMFont glyph check failed: ...` and
  nothing is written. A declared `scaleW`/`scaleH` that differs from the
  image is only reported (`scale_note` in `--json`). Zero-size glyphs
  (spaces) are accepted.
- `nav-to-godot`: a collider rectangle that covers a cell only in part
  is subtracted from that cell (exact axis-aligned cut: the cell is
  split along the collider edges and the free boxes are merged).
  `--min-piece PX` (default 1) drops thinner slivers;
  `--block-whole-cells` restores the 2.1.0 behaviour; a cell crossed by
  more than 64 colliders is blocked whole. Only rectangles are cut.
  Checked by a randomised area / non-overlap property test and a Godot
  4.7.2 load of the scene.
- `install.sh --venv` was run for real into a temporary prefix with an
  isolated HOME (Pillow 13.0.0 and numpy 2.5.5 from PyPI). With
  `--with-tests` it also installs `requirements-dev.txt` (pytest,
  fonttools) so `gst test` works in the venv. `--help` no longer prints
  the `set -euo pipefail` line. The suite covers the dry run always, and
  the real pip install when `GST_TEST_VENV=1`.

### Fixed

- `map-to-godot.load_map` and `map-objects-to-godot`: unusable JSON
  values (wrong types in layers, objects or tilesets) are a typed
  `GstInputError` instead of a raw `TypeError` / `ValueError`.
- `ase-json-import`: a clip whose durations sum to 0 no longer divides
  by zero; the same class of arithmetic errors is wrapped.
- `nav-to-godot`: enormous collider coordinates are a typed error
  instead of `OverflowError`.

### Tests and fuzz

- `tests/test_v22.py`: external TSX + image-collection + animation
  (maths, Godot software-GL render, resource read-back), shared tag
  expansion and repeat, glyph bounds for all three BMFont formats, nav
  cutting (including a 40-trial randomised property test and a Godot
  load), `install.sh` dry-run (and optional real venv), and a structured
  semantic fuzz of the new inputs.
- Fuzz seeds: new kinds `tsx`, `tiledanim`, `tmxext` and `asejson`, plus
  a partial-overlap collider seed. New catalog entries for
  `map-objects-to-godot-{anim,tmxext,tsx}` and `ase-json-import` (which
  was not fuzzed before). Official long fuzz (seed 1): 4060 cases, 0
  generic hits, 0 timeouts, 0 signals, 0 bad exits, 0 accepted-garbage.

## 2.1.0 — 2026-11-25

Closes gaps that were still open in existing tools. No new tools (262).

### Changed

- `map-objects-to-godot`: tile objects (those with a `gid`) now become
  `Sprite2D` nodes with `region_enabled` + `region_rect` from the tileset
  cell, `centered = false`, and the tileset image as an ExtResource.
  Tiled's H / V / diagonal flip flags become `flip_h`, `flip_v`, `rotation`
  and `scale` (a diagonal flip is `flip_v` plus a quarter turn), in Tiled's
  order. Width / height scale the tile, `rotation` turns it about the
  object's anchor, `tileoffset` and `objectalignment` are honoured. Verified
  in official Godot 4.7.2: a software-GL render of all eight flip
  combinations, a 2x diagonal-flipped tile and a rotated tile matches a
  Pillow reference pixel for pixel. Isometric maps are projected into screen
  space (positions, points and rectangles / ellipses / polygons /
  polylines as `CollisionPolygon2D`); staggered and hexagonal maps use
  Tiled's pixel coordinates. New flags `--res` and `--no-sprites`; the
  report gains `sprites`, `diagonal_sprites`, `unknown_gids`, `textures`,
  `orientation`. A GID outside every tileset stays a `Marker2D` carrying it.
- `ase-to-godot`: reverse, ping-pong and ping-pong-reverse tags are expanded
  into the frame list (no doubled end frames, so the loop is seamless), and
  a tag repeat count plays N cycles with `loop` off. Durations follow the
  expanded frames. `--ignore-direction` restores the old behaviour.
  `ase-decode` tags now also carry a `direction` name (the old `loop` key,
  which was Aseprite's direction byte, is kept). Verified in Godot 4.7.2:
  SpriteFrames frame order and `loop` read back from the generated `.tres`.
- `font-to-godot`: accepts binary BMFont v3 and XML BMFont as well as text.
  Binary loads in Godot 4.7.2 as is (its kerning applies). Godot 4.7.2 does
  not read XML BMFont (it loads as an empty font), so XML is converted to a
  text `.fnt` named `<stem>_text.fnt` and the Theme points at that. Multi-page
  fonts are checked and copied page by page.
- `nav-to-godot`: solids can come from tile-colliders output. `--colliders
  FILE` (rects JSON or `--tiled-objects`) marks the cells it covers as solid;
  with no `--solid-layer` / `--solid-ids`, a `<map stem>.colliders.json`
  (or `_colliders` / `-colliders`) next to the map is picked up
  automatically; `--no-colliders` turns that off. A collider file for a
  different tile size, or one that is not tile-colliders output, is a typed
  error. The report records `colliders` and `colliders_source`.
- zstd tile data is now decoded everywhere the kit reads Tiled layers
  (map-diff and everything that shares it, tmx-decode, tilemap-stats,
  map-clean, level-budget, tile-preview, tile-anim-gif, tmx-to-json). A
  native decoder is used when importable (`compression.zstd` on Python
  3.14+, `pyzstd`, `zstd`); otherwise the new stdlib-only `lib/zstd_pure.py`
  (RFC 8878: raw, RLE and compressed blocks with Huffman literals and FSE
  sequences, repeat offsets, content checksum verified, no dictionaries,
  32 MiB output cap). Checked against the reference zstd library on 504
  generated frames (levels 1 to 22, with and without checksum / content
  size), and against mutated frames: only `GstInputError` escapes. Writing
  zstd (`tmx-encode`) still needs one of the optional modules and says so
  in one line.

### Fixed

- `godot_text.res_path("res://", name)` produced `res://res:/name`; a bare
  `res://` prefix and a prefix that already names the file now work.
- `map-diff` / `tmx-to-json`: corrupt zlib or gzip tile data is a typed
  `GstInputError` instead of a raw `zlib.error`.
- `map-objects-to-godot`: a GID past the end of its tileset is reported as
  unknown instead of drawing a wrong cell.

### Tests and fuzz

- `tests/test_v21.py`: sprite transform maths for all eight flag
  combinations, a Godot software-GL pixel comparison, isometric projection,
  ase direction expansion (maths, `.tres` text, and Godot read-back),
  BMFont text / XML / binary (incl. a Godot load that checks kerning),
  nav colliders (auto pickup, flags, errors), zstd reference vectors,
  hand-built raw / RLE / direct-weight frames, checksums, limits, and a
  seeded mutation fuzz of the decoder.
- Fuzz seeds: the Tiled seed now carries object-layer tile objects, the ase
  seed has tags with direction and repeat, and new kinds cover XML and
  binary BMFont, collider files and zstd layers (JSON and TMX).

## 2.0.0 — 2026-11-25

### Added

- Batch 32 (8 tools), each filling a real handoff hole after batch 31:
  `map-objects-to-godot` (Tiled object layers become Node2D / Area2D /
  StaticBody2D scenes; map-to-godot still only reports objects),
  `hitbox-to-godot` (hitbox-gen JSON to per-frame Area2D + CollisionShape2D),
  `tile-colliders-to-godot` (tile-colliders or Tiled object JSON to a
  StaticBody2D scene), `nav-to-godot` (map-reach walkability to a
  NavigationRegion2D + NavigationPolygon), `nine-slice-to-godot` (image +
  insets to a StyleBoxTexture `.tres`), `font-to-godot` (text BMFont `.fnt`
  referenced from a Theme `.tres`; official Godot 4.7.2 loads the `.fnt`
  via ExtResource), `ase-to-godot` (binary Aseprite file to PNG frames plus
  a SpriteFrames `.tres` in one step), `data-to-godot` (CSV or JSON tables
  to a small Resource script + `.tres`).
- `map-to-godot` now maps Tiled H / V / diagonal flip flags to Godot
  TileSetAtlasSource alternative tiles (`flip_h` / `flip_v` / `transpose`).
  Alternative ids are stable: bit 0 = H, bit 1 = V, bit 2 = diagonal
  (transpose). Verified by loading a flipped-tile sample in official Godot
  4.7.2. The report key is `flipped_cells`.
- `loc-to-godot` gained `--translation-dir` and `--godot` (default
  `GODOT_BIN`). When official Godot is available, an isolated-HOME headless
  import of the translation CSV writes `<stem>.<locale>.translation`
  binaries (OptimizedTranslation). Without Godot, the tool writes loadable
  Translation `.tres` files and prints a note. Headless Godot 4.7.2 refuses
  a text-format `.translation` (binary only).

### Fixed

- Leftover generic-wrapper hits on official long `--debug` runs of this tree: `wav-loud-apply` (`MemoryError` allocating a 16 GiB FFT
  when a mutated WAV claimed a ~2^31 Hz sample rate; `gst_read.read_wav_frames`
  now rejects rates outside 1–768000 Hz and MemoryError is wrapped),
  `tile-dedupe` (`IndexError` when `--tile 8` was passed as a square size;
  a single number is now accepted as WxW, matching `tileset-from-image`),
  `glb-lod` and `glb-weld` (`IndexError` / `KeyError` on bit-flipped meshes
  whose indices fall outside the vertex table; `require_indices` raises
  `GstInputError`), and a follow-up `tile-dedupe` `ZeroDivisionError` when
  a truncated or undersized sheet yielded zero columns
  (`GstInputError: tileset is smaller than the tile size`).

### Notes

- 262 tools (254 + batch 32). Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
- Official long `--debug` numbers (seed 1, including `samples/` and the
  `fully-random` mutator; five mutators, so the natural set is 4000 cases
  rather than the 3000-case four-mutator set recorded after 1.9.0 leftover
  fixes): before these four leftover fixes, 4000 cases, 4 generic-wrapper
  hits, 0 timeouts, 0 signals, 0 bad exits, 0 accepted-garbage; after the
  fixes, 4000 cases, 0 generic-wrapper hits, 0 timeouts, 0 signals, 0 bad exits, 0 accepted-garbage. The 2984 traceback-class cases are validated input failures (GstInputError / SystemExit), not crashes.

## 1.9.0 — 2026-11-25

### Added

- Batch 31 (8 tools): `map-to-godot` (Tiled JSON/TMX to a Godot 4.x TileMapLayer
  `.tscn`, with optional TileSet `.tres`; `tile_map_data` layout verified against
  official Godot 4.7.2), `loc-to-godot` (loc CSV to Godot translation CSV),
  `ase-decode` (binary Aseprite `.ase` / `.aseprite` to PNG frames and tags JSON,
  no Aseprite app), `asset-unused` (files in a folder that no map, atlas, Godot
  scene or glTF references), `dialogue-lint` (Yarn/ink jumps to missing nodes,
  unmatched `[[` / `<<`, empty and orphan nodes), `godot-res-lint` (missing
  `res://` paths in `.tscn` / `.tres` / `.gd`), `texture-budget` (VRAM estimate
  and NPOT / max-edge flags for a texture folder), `anim-to-godot` (anim-meta
  clips plus a folder of frames to a SpriteFrames `.tres`).
- `gst fuzz` gained a `fully-random` mutator (a buffer of random bytes with no
  leftover structure from the seed). Reader tools must exit 1 or 2 on that
  input; exit 0 is classified as `accepted-garbage`. The suite asserts there
  are no accepted-garbage hits on the seeded fast set
  (`test_fuzz_fully_random_input_is_rejected`).

### Changed

- Shared image guards in `lib/gst_read.py` now wrap `DecompressionBombError`,
  `MemoryError`, `struct.error` and `IndexError` from Pillow `open` / `load`
  (and `seek`, except the `EOFError` Pillow uses to end an animation).
  `Image.MAX_IMAGE_PIXELS` is capped at 64e6 so a mutated header cannot
  allocate past the fuzz child's 512 MiB address-space limit.
  `load_loc_csv` normalises missing CSV cells (`None` on a short row) to empty
  strings.

### Fixed

- Leftover generic-wrapper hits on the long `--debug` set after 1.8.0: 
  `loop-finder` (`ValueError` from `numpy.frombuffer` on a truncated WAV),
  `palette-swap` (`int(..., 16)` on a JSON `--map` file; `--map` now also
  accepts a JSON object of colour mappings), `texture-resize` (`MemoryError`
  on a huge claimed size), `tile-extrude` (`cannot write empty image` when
  the sheet is smaller than the tile), `gif-optimize` (`IndexError` /
  `struct.error` on a truncated GIF), `gif-to-frames` (`DecompressionBombError`),
  `obj-to-glb` (out-of-range face index on an empty vertex table), `loc-check`
  (`None.strip()` on a short CSV row) and `pseudoloc` (`TypeError` on a
  `None` cell).
- `obj-weld`, `obj-clean-uv`, `obj-drop-unused`, `obj-merge` and
  `obj-triangulate` no longer exit 0 on an OBJ with no vertices (they raise
  `GstInputError: OBJ has no vertices`).

### Notes

- 254 tools (246 + batch 31). Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
- Official long `--debug` numbers (seed 1, 3000 cases, including `samples/`):
  after 1.8.0 readers and before the leftover fixes, 16 generic-wrapper hits;
  after those fixes, 0 generic-wrapper hits, 0 timeouts, 0 signals, 0 bad
  exits. A clean pre-validation long run was not captured (the earlier
  "before" report overlapped live 1.8.0 patches). On the seeded fast set,
  fully-random inputs are 194 cases with 0 accepted-garbage and 0 generic
  hits.

## 1.8.0 — 2026-11-25

### Added

- `GST_DEBUG=1` re-raises exceptions from `cli_error.run` and `gst run_tool`
  after the usual `SystemExit` / `KeyboardInterrupt` handling, so a developer
  or the fuzz classifier sees the real traceback. Values `0`, `false`, `False`,
  `no` and `NO` leave debug off. `gst fuzz --debug` sets `GST_DEBUG=1` in child
  processes and groups every caught exception by reader kind (WAV, PNG/GIF,
  Tiled JSON/TMX, GLB/glTF, OBJ, atlas JSON, loc CSV, Yarn/ink, BMFont) and
  root cause.
- `lib/gst_errors.py` (`GstInputError`) and `lib/gst_read.py`: shared, typed
  readers for the kit's common formats. Bad input raises `GstInputError` with a
  specific message, for example `WAV fmt chunk missing`, `WAV chunk length
  exceeds file`, `GLB chunk length exceeds file`, `GLB JSON chunk missing`,
  `Tiled layer data length mismatch`, `OBJ vertex line has invalid numbers`,
  `atlas JSON has no frames`, `CSV has no header row`, `file is not valid
  UTF-8`. `cli_error.run` also installs decoder guards around `json.load` /
  `json.loads`, `PIL.Image.open` (and pixel `load()`), `wave.open`,
  `xml.etree.ElementTree.parse` / `fromstring`, and text-mode `open`, so tools
  that call those libraries directly still raise `GstInputError` instead of a
  raw decoder exception.
- The fuzz suite asserts that generic-wrapper hits (a non-`GstInputError`
  `Exception` caught by `cli_error`) on the seeded fast set stay at or under 5
  (`tests/test_fuzz.py`). The existing "no traceback when `GST_DEBUG` is unset"
  check is unchanged. `tests/test_gst_read.py` covers the named messages
  above.

### Changed

- Shared readers in `audio_tidy.read_wav`, `wav_loop_meta`, `glb_lod.load_glb`,
  `mesh_pivot_fix.read_glb`, `gltf_inspect.load`, `obj_weld.load_obj`,
  `map_diff.decode_map` / `load_tsx`, `atlas_json.load`, `loc_merge.load_csv`
  (and the loc / dialogue / BMFont helpers that share them) now raise
  `GstInputError` for malformed input instead of leaking `wave.Error`,
  `JSONDecodeError`, `struct.error`, `StopIteration`, `UnicodeDecodeError` or
  a bare `SystemExit`.

### Fixed

- glTF / GLB files with no JSON chunk, a null document, or a chunk length
  past the end of the file no longer raise `AttributeError` (`None.get`) or
  `StopIteration` / `struct.error` in `glb-lod`, `glb-quantize`,
  `gltf-inspect`, `gltf-strip`, `mesh-pivot-fix` and the tools that reuse
  those loaders.
- `wav-loop-meta` no longer `StopIteration`s when the `fmt` or `data` chunk
  is missing; it raises `WAV fmt chunk missing` / `WAV data chunk missing`.
  WAV sample data whose length is not a multiple of the sample width, and
  `RuntimeError` from `wave.readframes` on a truncated file, become typed
  input errors.
- Localisation CSVs with no header no longer raise `TypeError` (`None` is
  not iterable) in `loc-check`, `loc-fit` and `pseudoloc`. `loc-plurals`
  no longer calls `.lower()` on a missing category or language name.
- `wfc-tiles` no longer raises `IndexError` / `KeyError` on an empty or
  jagged example, and it reads a Tiled JSON map as a tile layer instead of
  parsing it as CSV.
- OBJ tools no longer raise `ValueError` / `IndexError` on a short or
  non-numeric `v` / `vt` / `vn` line or an out-of-range face index
  (`obj-weld`, `obj-to-glb`, `obj-recenter` via `mesh-pivot-fix.fix_obj`,
  `obj-triangulate`, `obj-uv-unwrap`).
- `atlas-pack` given a file instead of a directory of images now raises
  a typed error instead of `NotADirectoryError`.
- `tile-extrude --tile` requires `WxH` (the fuzz catalog's `--tile 8` was
  also corrected to `8x8`). `palette-swap --map` accepts a file of
  `from:to` pairs and rejects a malformed map.

### Notes

- 246 tools (unchanged). Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor). On the seeded fast set (776 cases, seed 1)
  generic-wrapper hits went from 547 (every traceback in 1.7.0, hidden by the
  wrapper) to 0 after the readers and guards landed. `GstInputError` is a
  validated input failure, not a generic-wrapper hit.

## 1.7.0 — 2026-11-25

### Added

- Batch 30 (8 tools): `loc-fill` (fill empty localisation CSV cells from a
  source-language column; non-empty targets left alone unless `--overwrite`;
  optional `--prefix`; `--fail-if-empty` for CI), `map-outline` (4-connected
  outline of solid cells on a finite orthogonal Tiled JSON map, using the same
  walkability as `map-reach`; JSON, PNG overlay, and/or a copy with an
  `outline` tile layer), `obj-drop-unused` (drop unreferenced v / vt / vn and
  remap face and line corners; materials, groups and smoothing kept),
  `wav-limit` (peak limiter with `--ceiling-db`, attack and release; residual
  overshoot hard-clipped; length and rate unchanged; first `smpl` loop
  preserved), `sprite-align` (place sprites on one shared canvas so a common
  `--anchor` of each sprite's opaque content lines up; atlas rewrite updates
  `sourceSize` / `spriteSourceSize` and leaves packed pixels alone),
  `glb-extras-strip` (recursively strip every `extras` object from a .glb or
  .gltf; the binary buffer stays in place; animated / skinned / morphed files
  are allowed), `tmx-tileset-list` (list tilesets on a Tiled map, resolving
  external `.tsx` / `.tsj`; optional JSON / CSV; `--fail-if-none`),
  `atlas-merge` (unpack two or more atlas JSONs and repack with the atlas-pack
  packer; rotated frames refused; name collisions refused unless `--prefix` or
  `--prefer first`).
- Robustness pass: a stdlib-only fuzz harness at `tests/fuzz/` feeds empty,
  truncated, bit-flipped and random-byte inputs derived from tiny generated
  seeds (and, in long mode, from `samples/` when present) to every tool that
  reads WAV, PNG/GIF, Tiled JSON/TMX, GLB/glTF, OBJ, atlas JSON, CSV loc,
  Yarn/ink or BMFont. The seeded fast subset runs in the normal test suite
  (`tests/test_fuzz.py`). `gst fuzz --fast` / `gst fuzz --long` is a reserved
  kit command (`fuzz` cannot be a tool name). Requirement: no Python
  traceback; tools exit 0, 1 or 2 with a one-line error. A
  `lib/cli_error.py` wrapper (and a safety net in `gst run_tool`) catches
  unexpected exceptions in every tool's `__main__`.

### Changed

- Pipelines loc-pass, tiled-map-hygiene, gltf-cleanup, vo-slate-to-loudness
  and sprite-to-godot mention the new tools.

## 1.6.0 — 2026-11-25

### Added

- Batch 29 (8 tools): `loc-stats` (key counts, per-language fill rates,
  character and word counts, longest strings, duplicate keys; the CSV is not
  rewritten; `--fail-if-empty-gt` for CI), `map-path` (A* on a finite
  orthogonal Tiled JSON map using the same walkability as `map-reach`; JSON
  and optional PNG overlay; `--fail-if-none`), `obj-clean-uv` (clamp vt to
  [0,1], weld within an epsilon, drop unreferenced vt, remap face corners),
  `wav-gate` (noise gate with attack / hold / release; length and rate
  unchanged; the first `smpl` loop is preserved), `sprite-reframe` (place each
  sprite on a new `--size WxH` source canvas; atlas rewrite updates
  `sourceSize` / `spriteSourceSize` and leaves packed pixels alone; clipping
  and rotated packed frames are refused), `glb-attr-rename` (`--map` or
  `--pattern` / `--replace`; POSITION cannot be renamed; collisions refused;
  accessors stay in place; animated / skinned / morphed meshes are refused),
  `tmx-anim-list` (list `tiles[].animation` from a Tiled map or tileset,
  resolving external `.tsx` / `.tsj`; optional JSON / CSV; `--fail-if-none`),
  `atlas-sort` (sort frames by name, position or size; the sheet image is not
  rewritten).
- A third showcase at `examples/showcase-web/`: a dependency-free HTML5
  canvas game (vanilla JS, no CDN, no npm) whose tiles, Tiled JSON map, player
  atlas, coin WAV and BMFont all come from kit generators. A reusable loader
  (`js/gst-loader.js`, plus an ESM façade) parses those formats in the browser
  and in Node. `map-path` verifies the coin is reachable at build time. A
  headless test parses the assets with Node and screenshots the first frame
  via CutyCapt / Xvfb (the same path used for the docs-site screenshot).
  Preview GIF and PNGs live under `examples/showcase-web/preview/`.

### Changed

- Pipelines loc-pass, tiled-map-hygiene, gltf-cleanup, vo-slate-to-loudness
  and sprite-to-godot mention the new tools. A `web-showcase` pipeline doc
  was added. The docs site showcase page now includes all three previews.

### Notes

- 238 tools. Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
  not in the kit tarball. The two Godot showcases are unchanged.

## 1.5.0 — 2026-11-25

### Added

- Batch 28 (8 tools): `loc-join` (inverse of `loc-split`; union of keys, first-wins
  on duplicate keys, first non-empty across files for the same language),
  `map-blank` (empty finite orthogonal Tiled JSON map, no input file),
  `obj-validate` (out-of-range indices and degenerate faces are errors;
  unreferenced vertices are warnings, `--strict` fails on warnings),
  `wav-silence` (generate, insert at `--at`, or `--replace START,END`; first
  `smpl` loop is preserved and shifted on insert), `sprite-unpad` (inverse of
  `sprite-pad`; atlas rewrite shrinks `sourceSize` and `spriteSourceSize`,
  packed rects stay put; a pad that would clip packed content is refused),
  `glb-attr-drop` (drop named vertex attributes from a static GLB; POSITION
  cannot be dropped; animated / skinned / morphed meshes are refused),
  `tmx-gid-usage` (per-GID counts with flip flags and unused tileset reports;
  tile layers only), `atlas-rename` (`--map` or `--pattern` / `--replace`;
  collisions refused; the sheet image is not rewritten).
- A second Godot 4.7 showcase at `examples/showcase-platformer/`: side-view
  platformer, all runtime art from kit generators, 3-tile gaps validated by
  `jump-arc` against the game's gravity (800), jump velocity (220) and speed
  (120). One-way and solid colliders from `godot-tileset`, a coin pickup SFX,
  parallax layers (also previewed with `parallax-preview`), and a generated
  BMFont HUD. `./build_showcase.sh` rebuilds the assets; a headless Godot
  integration test walks, jumps the first gap, and asserts a landing
  (`GST_PLATFORMER_OK`). A software-GL preview GIF is recorded when a display
  or xvfb is available. Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).

### Changed

- `jump-arc --json` now also reports `end: [x, y]` and `out_of_bounds`.
  Leaving the map still sets `landed` to true (same as before), so a platform
  landing should be checked against `end` and `out_of_bounds`, not `landed`
  alone.
- Pipelines loc-pass, tiled-map-hygiene, gltf-cleanup, vo-slate-to-loudness,
  sprite-to-godot and godot-showcase mention the new tools and the second
  showcase. The docs site showcase page now includes both previews.

### Notes

- 230 tools. Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
  not in the kit tarball. The 1.2.0 top-down showcase preview is unchanged.
  The docs site is built beside the kit at `gamestudio-tools-site/`
  and is not packed into the tarball.

## 1.4.0 — 2026-11-25

### Added

- Batch 27 (8 tools): `loc-split` (per-language CSVs, first-wins on duplicate
  keys), `map-pad` (empty-tile border; objects and image layers shift with the
  left/top pad; inverse of `map-crop` without a used-tile shrink), `obj-flip`
  (mirror across `--axis x|y|z` and reverse face winding so the mesh does not
  go inside-out), `wav-gain` (fixed dB gain, optional `--max-true-peak` cap
  via the uncertified wav-batch-meta meter, `smpl` loops kept), `sprite-pad`
  (per-sprite canvas padding, not the between-frame padding of `sheet-pad`),
  `glb-quantize` (snap POSITION/NORMAL/TEXCOORD floats; normals renormalised),
  `tmx-layer-filter` (`--keep` or `--drop` fnmatch globs, groups walked),
  `palette-apply` (nearest colour or Floyd–Steinberg; `.hex` / `.gpl` / image
  / pixelize built-in palettes).
- `sprite-rotate` and `sprite-scale` rewrite an atlas JSON when `--atlas` or a
  `.json` input is given: packed sheet pixels plus every frame rect,
  sourceSize, spriteSourceSize, `meta.size` and `meta.image`. Packed rewrite
  is 90/180/270 only for rotate; `--size` on scale is the new sheet size.
  Frames with `rotated: true` are refused.
- `gst docs -o DIR`: a reserved command (not a 223rd tool) that builds a
  static, dependency-free HTML docs site from every tool README, the
  pipelines, the category list, CHANGELOG and the showcase previews.
  Searchable index (client-side JS, index inlined so `file://` works, no CDN),
  per-tool pages, dark theme, system fonts. A test checks that every tool has
  a page and that internal links resolve.

### Changed

- Pipelines tiled-map-hygiene, loc-pass, gltf-cleanup, vo-slate-to-loudness
  and sprite-to-godot mention the new tools and the atlas rewrite.

### Notes

- 222 tools. Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
  not in the kit tarball. The 1.2.0 showcase project and its software-GL
  preview GIF are unchanged. The docs site is built beside the kit at
  `gamestudio-tools-site/` and is not packed into the tarball.

## 1.3.0 — 2026-11-25

### Added

- Batch 25 (8 tools): `tmx-decode` (inverse of `tmx-encode`), `loc-diff`,
  `map-chunk` (plus an optional Tiled `.world`), `obj-decimate` (vertex
  clustering), `wav-resample` (scales `smpl` loops), `sprite-rotate`
  (exact 90/180/270, nearest-neighbour otherwise), `tileset-renumber`
  (local ids and optional map GIDs, flip flags kept), `glb-center`
  (glTF counterpart of `obj-recenter`, default `--mode center`).
- Batch 26 (8 tools): `loc-rename`, `map-shift`, `obj-subdivide` (midpoint,
  watertight shared edges), `wav-invert`, `sprite-scale` (nearest-neighbour),
  `glb-weld` (static GLB counterpart of `obj-weld`), `tmx-world` (from
  `chunk_x`/`chunk_y`, `_X_Y` filenames, or a grid), `wav-mono`.
- Batch 27 is queued (not built in this cut): `loc-split`, `map-pad`,
  `obj-flip`, `wav-gain`, `sprite-pad`, `glb-quantize`, `tmx-layer-filter`,
  `palette-apply`.

### Changed

- `sfx-normalize` accepts `--lufs TARGET` and `--max-true-peak` (default
  `-1.0` dBTP), reusing the uncertified ITU-R BS.1770-4 meter in
  `wav-batch-meta` / `wav-loud-apply`. The default remains a sample-peak
  dBFS pass; `smpl` loops are still preserved.
- Pipelines tiled-map-hygiene, loc-pass, gltf-cleanup, vo-slate-to-loudness
  and sprite-to-godot mention the new tools.

### Notes

- 214 tools. Official Godot is not in the kit tarball (set GODOT_BIN to a Godot 4.7.2 editor).
  not in the kit tarball. The 1.2.0 showcase project and its software-GL
  preview GIF are unchanged.

## 1.2.0 — 2026-11-25

### Added

- `examples/showcase-godot/`: a minimal top-down Godot 4.7 project whose every
  runtime asset is produced by kit procedural generators (`tex-gen`,
  `tileset-gen`, `tileset-wang`, `godot-tileset`, `dungeon-gen`, `tile-colliders`,
  `pixelize`, `sprite-outline-gen`, `sprite-canvas`, `sprite-shadow`,
  `anim-from-folder`, `atlas-pack`, `atlas-to-godot`, `sfx-gen`, `sfx-normalize`,
  `wav-loud-apply`, `bmfont-gen`, `godot-import-presets`, and for the preview
  `frames-to-sheet`, `spritesheet-gif`, `gif-optimize`). `build_showcase.sh`
  wipes and regenerates `art/`, `sfx/`, `font/` and `preview/` from scratch.
- Integration tests in `tests/test_showcase_godot.py`: the asset rebuild always
  runs; the headless import + wall-collision run (prints `GST_SHOWCASE_OK`) and
  the software-GL preview GIF are exercised when `GODOT_BIN` is set.
- Pipeline doc `docs/pipelines/godot-showcase.md`. Batch 25 is queued (not built
  in this cut): `tmx-decode`, `loc-diff`, `map-chunk`, `obj-decimate`,
  `wav-resample`, `sprite-rotate`, `tileset-renumber`, `glb-center`.

### Changed

- `gst bundle` and `install.sh` skip `.godot` editor caches and `.uid` files so
  a built showcase can be packed without the import cache.
- The tileset-to-godot pipeline notes now match 1.1.0: `godot-tileset` does emit
  physics polygons, terrain sets and compact-grid animations.

### Notes

- Official Godot 4.7.2 (`4.7.2.stable.official.ed1daf0bf`, under
  a Godot 4.7.2 editor, not in the kit tarball) imported the showcase,
  ran the main scene headless, and confirmed a `CharacterBody2D` walking into a
  wall tile is stopped by tileset physics (`GST_SHOWCASE_OK`). Preview frames and
  `preview/showcase.gif` were recorded with `LIBGL_ALWAYS_SOFTWARE=1` and
  `--rendering-method gl_compatibility` (`--write-movie`); `--headless` uses the
  dummy renderer and cannot draw those frames.
- The BMFont uses Pillow's bundled default face (no vendored TTF). Solid walls
  use atlas tile 47 (stamped dirt); blob tile 0 is an isolated grass cap.
- 198 tools (unchanged). The showcase is an example, not a new `gst` tool.

## 1.1.0 — 2026-11-25

### Added

- Batch 24 (8 tools): `loc-merge`, `map-scale`, `obj-split`, `sfx-normalize`,
  `tileset-split`, `wav-chan-swap`, `sprite-recolor`, `tmx-encode`.
- All 8 tools are in `gst` categories and `gst search`, honour the kit-wide
  `--in-place` overwrite policy, and have self-contained tests (no `samples/`
  dependency). Loc, Tiled-map, glTF, VO, tileset and sprite pipelines pick them
  up where they fit.

### Changed

- `godot-tileset` now emits physics collision polygons (from a per-tile Tiled
  objectgroup or `--colliders` in tileset-sheet space), terrain sets (from
  embedded or `--wang` wangsets) and tile animations when the frame ids form a
  compact atlas grid. Official Godot 4.7.2.stable.official.ed1daf0bf loaded a
  sample TileSet with a physics layer, MATCH_SIDES terrain peering, and a
  2-frame animation (durations 1 and 2 at speed 10).
- `atlas-to-godot` unpacks rotated atlas frames (TexturePacker/Aseprite 90° CW)
  into sibling PNGs and references them as ExtResource. Official Godot 4.7.2
  loaded an unpacked 8×12 frame. A readable sheet is still required; other
  rotation angles are not inferred.

### Notes

- The same official Godot 4.7.2 binary (`4.7.2.stable.official.ed1daf0bf`, under
  a Godot 4.7.2 editor, not in the kit tarball) also still loads the
  existing SpriteFrames walk clip, 47-tile TileSet, pixel PNG and wav-oneshot
  WAV emitters.
- Tiled animations that are not a compact atlas grid are skipped. Ellipse
  colliders are approximated as a 12-gon. `--colliders` is tileset-sheet space,
  not a level map.
- zstd-encoded Tiled tile data is still only decoded or written when
  `compression.zstd` (Python 3.14+), `pyzstd`, or `zstd` is importable.
- `sfx-normalize` is a sample peak (dBFS), not LUFS or true-peak.

## 1.0.0 — 2026-11-25

### Added

- Batch 23 (8 tools): `sfx-reverse`, `loc-key-lint`, `map-mirror`, `obj-merge`,
  `anim-from-folder`, `wav-loop-snap`, `tileset-merge`, `glb-uv-transform`.
- All 8 tools are in `gst` categories and `gst search`, honour the kit-wide
  `--in-place` overwrite policy, and have self-contained tests (no `samples/`
  dependency). Sprite, Tiled-map, loc, VO, tileset and glTF pipelines pick them
  up where they fit.
- Optional integration test `tests/test_godot_load.py`, run when `GODOT_BIN` is
  set to a Godot 4 editor binary. It builds a temp project from `godot-import-presets`,
  `godot-tileset` and `atlas-to-godot`, then opens it with `--headless --import`
  and a verify script.

### Changed

- `godot-import-presets` glob matching is now path-style: `*` is one path
  segment and `**` matches zero or more directories, so `art/**/*.png` matches
  files in `art/` itself as well as in subfolders. (`fnmatch` treated `**` as two
  stars and only matched files with an extra directory.)

### Notes

- Official Godot 4.7.2 (Linux x86_64 editor, `4.7.2.stable.official.ed1daf0bf`)
  loaded the kit's SpriteFrames `.tres`, TileSet `.tres`, `.import` sidecars
  (pixel PNG and wav-oneshot WAV) and the referenced textures / AudioStreamWAV
  with no format errors. The editor fills in `uid` / `path` / `dest_files` on
  `.import` files, as documented. The Godot binary lives on the box under
  a Godot 4.7.2 editor and is not in the kit tarball.
- zstd-encoded Tiled tile data is still only decoded when `compression.zstd`
  (Python 3.14+), `pyzstd`, or `zstd` is importable.
- LUFS uses the same uncertified ITU-R BS.1770-4 meter as `wav-batch-meta`.
- `map-mirror` supports orthogonal finite maps; hexagonal / isometric / infinite
  maps are refused. `glb-uv-transform` refuses sparse accessors and external
  (non-data-URI) buffers.
- 190 tools. 254 tests (the Godot load test is skipped unless `GODOT_BIN` is set).

## 0.9.0 — 2026-11-25

### Added

- Batch 21 (8 tools): `glb-split`, `loc-icu-extract`, `map-auto-layer`, `obj-normals`,
  `anim-hold`, `wav-fade`, `sprite-stack`, `tmx-object-types`.
- Batch 22 (8 tools): `loc-sort`, `map-fill`, `obj-bounds`, `anim-rename`,
  `wav-pad`, `sprite-canvas`, `tmx-layer-opacity`, `map-rotate`.
- All 16 tools are in `gst` categories and `gst search`, honour the kit-wide
  `--in-place` overwrite policy, and have self-contained tests (no `samples/`
  dependency). Sprite, Tiled-map, loc, VO and glTF pipelines pick them up where
  they fit.

### Changed

- `obj-triangulate` now ear-clips n-gons so concave faces stay inside the original
  polygon. Self-intersecting or degenerate faces fall back to a triangle fan and
  are counted as `fan_fallback` in the JSON report.

### Notes

- zstd-encoded Tiled tile data is still only decoded when `compression.zstd`
  (Python 3.14+), `pyzstd`, or `zstd` is importable.
- Godot `.tres` / `.import` files are not loaded in a Godot editor (none on the
  box). LUFS uses the same uncertified ITU-R BS.1770-4 meter as `wav-batch-meta`.
- `map-rotate` supports orthogonal finite maps; hexagonal / isometric / infinite
  maps are refused. `glb-split` refuses external (non-data-URI) buffers.
- 182 tools. 245 tests.

## 0.8.0 — 2026-11-25

### Added

- Overwrite policy, kit-wide: a tool that would write its input now refuses unless an
  explicit `--in-place` flag is given. `wav-loop-meta set` / `clear` / `from-json` no
  longer default to overwriting. Shared helper `lib/safe_out.py`. 139 of the 150 tools
  in 0.7.0 gained the flag and a dest==src check; the other 11 are generators with no
  input file, or tools that already had a different consent flag (`asset-rename --apply`,
  `godot-import-presets --force` for `.import` sidecars). Covered by `tests/test_overwrite.py`
  (static audit of every tool, plus behavioural tests for wav-loop-meta, a required `-o`
  writer, and audio-tidy writing into the source directory).
- Batch 19 (8 tools): `atlas-unpack`, `map-layer-merge`, `loc-plurals`, `obj-triangulate`,
  `anim-pingpong`, `tmx-embed-tileset`, `cubemap-pack`, `nav-grid`.
- Batch 20 (8 tools): `map-layer-split`, `ldtk-to-tiled`, `obj-transform`, `anim-splice`,
  `tmx-infinite-to-finite`, `sfx-pitch`, `sprite-trim`, `glb-merge`.
- All 16 tools are in `gst` categories and `gst search`. Sprite, Tiled-map and loc pipelines
  pick up unpack / merge+nav-grid / plurals respectively.

### Changed

- The 0.7.0 note that in-place metadata writers were an exception to "never overwrite the
  input" is withdrawn: those tools now require `--in-place` (or a distinct output path).

### Notes

- zstd-encoded Tiled tile data is still only decoded when `compression.zstd`
  (Python 3.14+), `pyzstd`, or `zstd` is importable.
- Godot `.tres` / `.import` files are not loaded in a Godot editor (none on the
  box). LUFS uses the same uncertified ITU-R BS.1770-4 meter as `wav-batch-meta`.
- `sfx-pitch` is linear-interpolation resampling (pitch and duration are locked);
  it is not a phase vocoder. `glb-merge` refuses external (non-data-URI) buffers.
- 166 tools. 227 tests.

## 0.7.0 — 2026-11-25

### Added

- Batch 18 (8 tools): `tile-replace`, `atlas-to-godot`, `wav-dc-remove`,
  `map-layer-rename`, `prefab-index`, `obj-recenter`, `anim-reverse`, `loc-missing`.
- `gst search [KEYWORD...]` and `gst list --category CAT`, plus `gst categories`.
  Every tool has a primary category (audio, maps, sprites, mesh, dialogue, loc,
  fonts, images, animation, terrain, data, godot) and a one-line description.
- Six documented end-to-end pipelines in `docs/pipelines/`, each covered by an
  integration test in `tests/test_pipelines.py`:
  sprite art → padded atlas → Godot SpriteFrames; Tiled lint → clean → crop →
  stats; VO script → slate → DC-remove → trim → loudness; glTF strip → rename →
  pivot → material audit; loc missing → placeholders → check; tileset-gen →
  wang → Godot TileSet.
- This changelog.

### Changed

- Kit-wide exit-code convention, documented in `gst --help` and the README:
  0 success, 1 issues / CI fail, 2 usage error. 38 early tools that fell off
  `main()` with `None` now `return 0`, and their `__main__` blocks call
  `sys.exit(main())`.
- `gst bundle` requires `-o/--out` and honours `--help` (it no longer writes a
  tarball into the current directory when invoked with leftover or help args).
- `gst list` prints `[category]` next to each one-line description.
- `atlas-to-godot` accepts clip frame names with or without a `.png` suffix, so
  it matches both TexturePacker-style names and the stems written by `atlas-pack`.

### Notes

- In-place metadata writers (notably `wav-loop-meta set` / `clear` when `-o` is
  omitted) remain an exception to the "never overwrite the input" rule.
- zstd-encoded Tiled tile data is still only decoded when `compression.zstd`
  (Python 3.14+), `pyzstd`, or `zstd` is importable.
- Godot `.tres` / `.import` files are not loaded in a Godot editor (none on the
  box). LUFS uses the same uncertified ITU-R BS.1770-4 meter as `wav-batch-meta`.

## 0.6.0 — 2026-11-25

Batch 16 (`wav-chan-split`, `dialogue-to-yarn`, `tileset-wang`, `glb-rename-nodes`,
`sheet-pad`, `sfx-envelope`, `map-reorder`, `gif-optimize`) and batch 17
(`map-crop`, `dialogue-to-ink`, `sprite-flip-sheet`, `tmx-props-lint`,
`contact-sheet`, `curve-trace`, `godot-tileset`, `wav-gap-squeeze`). 142 tools.

Gap closures: `map-clean` packs firstgids and remaps GIDs unless `--keep-firstgids`;
`obj-weld` keeps `mtllib` / `usemtl` / group / smoothing / comment lines; zstd tile
data is decoded when a zstd library is importable.

## 0.5.0 — 2026-11-25

Batches 14–15. Encoded base64 zlib/gzip/csv tile data decoded in the map tools;
external `.tsx` / `.tsj` tilesets resolved in `tile-anim-gif` and `tile-preview`.

## 0.4.0 — 2026-11-24

Batches 12–13.

## 0.3.0 / 0.2.0 — 2026-11-24

Earlier kit cuts covering batches 1–11, plus the `gst` entry point and `install.sh`.
