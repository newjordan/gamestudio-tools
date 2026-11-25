# Tiled map lint, clean, crop, stats

Lint object properties against a schema, drop hidden/empty layers and unused tilesets (repacking
firstgids), crop to used tiles, then print stats. Useful as a CI pre-commit chain on room prefabs.

## Tools

tmx-embed-tileset (when the map references external .tsx) → tmx-decode (if tile data is still encoded) → tmx-props-lint → tmx-object-types → map-clean → map-crop → tilemap-stats, plus map-layer-merge, map-auto-layer, map-fill, tmx-layer-opacity, map-rotate, map-mirror, map-scale, map-shift, map-pad, map-blank, map-chunk, tmx-world, tileset-renumber, tmx-layer-filter, tmx-gid-usage, tmx-anim-list, tmx-tileset-list, map-path, map-outline, tmx-encode and nav-grid when a room needs a single collision layer, decoration, a fill, visibility tweaks, a rotation, a mirror, a tile-size scale, a tile/object nudge, an empty-tile border, a blank map, chunked world files, a local-id renumber, a layer keep/drop, a GID usage report, a tile-animation listing, a tileset list, a walkable A* path, a solid-cell outline, a data re-encode, or a walkability preview

## Commands

```bash
mkdir -p /tmp/pipe-map
gst tmx-props-lint samples/pipelines/maps/level.json --schema samples/pipelines/maps/props.schema.json
gst map-clean samples/pipelines/maps/level.json -o /tmp/pipe-map/clean.json --pretty
gst map-crop /tmp/pipe-map/clean.json -o /tmp/pipe-map/crop.json --margin 1 --pretty
gst tilemap-stats /tmp/pipe-map/crop.json --json /tmp/pipe-map/stats.json
gst tmx-object-types lint /tmp/pipe-map/crop.json --types samples/pipelines/maps/objecttypes.xml
gst map-auto-layer /tmp/pipe-map/crop.json --rules samples/pipelines/maps/auto-rules.json -o /tmp/pipe-map/deco.json
gst tmx-layer-opacity /tmp/pipe-map/deco.json -o /tmp/pipe-map/faded.json --set deco=0.8
# optional: gst map-blank -o /tmp/pipe-map/blank.json --size 32x12 --tile 16
# optional: gst tmx-gid-usage /tmp/pipe-map/level.json --json /tmp/pipe-map/gid.json
# optional: gst tmx-anim-list /tmp/pipe-map/level.json --json /tmp/pipe-map/anims.json
# optional: gst map-path /tmp/pipe-map/level.json --start-name spawn --goal-name exit --json /tmp/pipe-map/path.json --fail-if-none
# optional: gst tmx-tileset-list /tmp/pipe-map/level.json --json /tmp/pipe-map/tilesets.json
# optional: gst map-outline /tmp/pipe-map/level.json --json /tmp/pipe-map/outline.json --png /tmp/pipe-map/outline.png
# optional: gst map-fill ... / gst map-rotate ... --degrees 90 / gst map-mirror ... --axis h / gst map-scale ... --factor 2 / gst map-shift ... --tiles 1,0 / gst map-pad ... --margin 1 / gst tmx-layer-filter ... --drop 'tmp_*' / gst tmx-decode ... --encoding array / gst map-chunk ... --size 16x16 --world /tmp/pipe-map/level.world / gst tmx-world /tmp/pipe-map/chunks -o /tmp/pipe-map/level.world / gst tileset-renumber ... --offset 10 / gst tmx-encode ... --encoding csv
```

`tmx-props-lint` exits 1 when a required property is missing or mistyped. `map-clean` remaps
firstgids unless you pass `--keep-firstgids`. `tilemap-stats --fail-on-unused-tileset` is a useful
CI flag after the clean step.

## Known gaps

zstd-encoded tile data is only decoded when a zstd library is importable. External `.tsx` tilesets
are resolved by some map tools but are not required for this chain (the sample map is self-contained).
