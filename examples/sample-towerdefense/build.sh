#!/usr/bin/env bash
# Reed Causeway: rebuild every generated asset of the tower-defense sample with gst.
# Authored inputs: src/*.py (pixel drawings, map objects, music, the combat sim),
# data/* (CSV/JSON, loc, DejaVu font), project/project.godot, scenes and scripts.
# Generated (wiped and rewritten here): project/{art,levels,ui,audio,data,i18n}
# and work/ (intermediates, reports, previews). Godot steps need GODOT_BIN (4.7+).
#
#   bash build.sh            # assets only
#   bash build.sh --verify   # + headless import, autoplay clear, save-file lint
#   bash build.sh --movie    # + verify + software-GL --write-movie -> media/
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -n "${GST_ROOT:-}" ] && [ -x "${GST_ROOT}/gst" ]; then
  gst() { python3 "$GST_ROOT/gst" "$@"; }
elif [ -x "$HERE/../../gst" ]; then
  GST_ROOT="$(cd "$HERE/../.." && pwd)"
  gst() { python3 "$GST_ROOT/gst" "$@"; }
elif command -v gst >/dev/null 2>&1; then
  :
else
  echo "build.sh: gst not found (set GST_ROOT, install the kit, or run from a checkout)" >&2
  exit 2
fi
MODE="${1:-}"
P="$HERE/project"
W="$HERE/work"
cd "$HERE"

godot_env() {
  # Isolate Godot's HOME only for the editor process. Exporting HOME for the
  # rest of the script hides the user site-packages (Pillow) from later gst steps.
  local home="${GST_GODOT_HOME:-}"
  if [ -z "$home" ]; then
    home="$(mktemp -d "${TMPDIR:-/tmp}/gst-sample-towerdefense.XXXXXX")"
    GST_GODOT_HOME="$home"; export GST_GODOT_HOME
    trap 'rm -rf "$GST_GODOT_HOME"' EXIT
  fi
  mkdir -p "$home/.config" "$home/.local/share" "$home/.cache"
}

godot_run() {
  env HOME="$GST_GODOT_HOME" \
    XDG_CONFIG_HOME="$GST_GODOT_HOME/.config" \
    XDG_DATA_HOME="$GST_GODOT_HOME/.local/share" \
    XDG_CACHE_HOME="$GST_GODOT_HOME/.cache" \
    "$@"
}

rm -rf "$P/art" "$P/levels" "$P/ui" "$P/audio" "$P/data" "$P/i18n" "$P/.godot" "$W"
mkdir -p "$P/art/creeps" "$P/art/puff" "$P/levels" "$P/ui" "$P/audio/sfx" "$P/data" "$P/i18n" \
  "$W/raw" "$W/tiles/sheet" "$W/maps" "$W/towers" "$W/creep" "$W/audio/gen" "$W/audio/dc" \
  "$W/audio/trim" "$W/audio/mono" "$W/audio/rs" "$W/audio/fade" "$W/audio/pitch" "$W/audio/gain" \
  "$W/audio/limit" "$W/audio/music" "$W/preview" "$W/reports" "$W/font" "$W/loc" "$W/icon"
printf '*\n' > "$W/.gdignore"

echo "== 1. tiles: tex-gen grass, bricks and water, drawn mill, frames-to-sheet =="
python3 src/make_art.py -o "$W/raw"
gst tex-gen noise  -o "$W/tiles/sheet/t00_grass.png" --size 16 --seed 11 --color-a 3f6b3a --color-b 2a4a28
gst tex-gen bricks -o "$W/tiles/sheet/t01_path.png"  --size 16 --seed 11 --count 2 --color-a c4a574 --color-b 8a6a40 --mortar-color 6b5030
gst tex-gen noise  -o "$W/tiles/sheet/t02_water.png" --size 16 --seed 13 --color-a 2a5a78 --color-b 163848
cp "$W/raw/tiles/t03_core.png" "$W/tiles/sheet/t03_core.png"
gst frames-to-sheet "$W/tiles/sheet" -o "$P/art/tiles" --columns 4 --no-crop
gst autotile-gen "$W/raw/autotile.png" --tile 16 -o "$W/tiles/auto"
gst tileset-wang --kind edge --image "$P/art/tiles.png" -o "$W/tiles/wang.json" --tile 16 --columns 4
gst tile-extrude "$P/art/tiles.png" -o "$W/tiles/tiles_extrude.png" --tile 16x16 --extrude 1
gst wfc-tiles "$W/raw/wfc.csv" -o "$W/maps/wfc.csv" --size 12x8 --seed 11
gst godot-tileset "$P/art/tiles.png" -o "$W/maps/tileset_alt.tres" --tile 16 --columns 4 --res res://art/tiles.png --no-collision

echo "== 2. causeway: map-blank, map-fill grass/water/road, layout objects =="
gst map-blank -o "$W/maps/m0.json" --size 20x12 --tile 16 --layers ground,path \
  --tileset ../art/tiles.png --tileset-name tiles --tilecount 4 --columns 4
gst map-fill "$W/maps/m0.json" -o "$W/maps/m1.json" --layer ground --gid 1 --rect 0,0,20,12
gst map-fill "$W/maps/m1.json" -o "$W/maps/m2.json" --layer ground --gid 3 --rect 0,0,20,1
gst map-fill "$W/maps/m2.json" -o "$W/maps/m3.json" --layer ground --gid 3 --rect 0,11,20,1
gst map-fill "$W/maps/m3.json" -o "$W/maps/m4.json" --layer ground --gid 3 --rect 2,4,2,1
gst map-fill "$W/maps/m4.json" -o "$W/maps/m5.json" --layer ground --gid 3 --rect 8,4,3,1
gst map-fill "$W/maps/m5.json" -o "$W/maps/m6.json" --layer ground --gid 3 --rect 17,3,2,1
gst map-fill "$W/maps/m6.json" -o "$W/maps/m7.json" --layer ground --gid 3 --rect 17,7,2,1
gst map-fill "$W/maps/m7.json" -o "$W/maps/m8.json" --layer path --gid 2 --rect 0,2,16,1
gst map-fill "$W/maps/m8.json" -o "$W/maps/m9.json" --layer path --gid 2 --rect 15,2,1,5
gst map-fill "$W/maps/m9.json" -o "$W/maps/m10.json" --layer path --gid 2 --rect 4,6,12,1
gst map-fill "$W/maps/m10.json" -o "$W/maps/m11.json" --layer path --gid 2 --rect 4,6,1,4
gst map-fill "$W/maps/m11.json" -o "$W/maps/m12.json" --layer path --gid 2 --rect 4,9,16,1
python3 src/layout.py "$W/maps/m12.json" -o "$P/levels/causeway.json" --rules data/rules.json --build data/build.csv

echo "== 3. route, combat sim, map checks =="
PTS="$(python3 -c 'import json; r=json.load(open("data/rules.json")); print(";".join("%d,%d" % tuple(p) for p in r["points"]))')"
gst curve-gen --points "$PTS" --kind linear --spacing 8 --json "$P/data/route.json"
gst curve-trace --points "$PTS" --kind linear -o "$W/preview/route.png" --width 320 --height 192
python3 src/sim.py --route "$P/data/route.json" --rules data/rules.json \
  --towers data/towers.csv --creeps data/creeps.csv --waves data/waves.csv --build data/build.csv \
  -o "$P/data/combat.json"
cp data/rules.json "$P/data/rules.json"
gst map-path "$P/levels/causeway.json" --start-name spawn --goal-name core --ground-layer path --fail-if-none \
  --png "$W/preview/path.png" --scale 2 --json "$W/reports/path.json"
gst map-reach "$P/levels/causeway.json" --start-name spawn --ground-layer path --require core \
  --json "$W/reports/reach.json"
gst tmx-props-lint "$P/levels/causeway.json" --schema data/map_props.schema.json --md "$W/reports/props.md"
gst level-budget "$P/levels/causeway.json" --budget data/level_budget.json --fail-on-under --md "$W/reports/budget.md"
gst tilemap-stats "$P/levels/causeway.json" --fail-on-empty-layer --csv "$W/reports/tilemap_stats.csv"
gst tmx-objects-csv "$P/levels/causeway.json" -o "$W/reports/objects.csv"
gst tmx-gid-usage "$P/levels/causeway.json" --json "$W/reports/gid_usage.json" --fail-on-unused-tileset
gst tmx-tileset-list "$P/levels/causeway.json" --json "$W/reports/tilesets.json" --fail-if-none
gst tilemap-convert stats "$P/levels/causeway.json"
gst tilemap-convert to-csv "$P/levels/causeway.json" -o "$W/maps/causeway"
gst room-graph "$P/levels/causeway.json" --start gate --fail-on-unreachable \
  --mermaid "$W/reports/rooms.mmd" --dot "$W/reports/rooms.dot" --json "$W/reports/rooms.json"
gst nav-grid "$P/levels/causeway.json" -o "$W/preview/nav.png" --ground-layer path --start 0,2
gst map-outline "$P/levels/causeway.json" --png "$W/preview/outline.png" --ground-layer path
cp "$P/levels/causeway.json" "$W/maps/rename_in.json"
gst map-layer-rename "$W/maps/rename_in.json" --pattern '^path$' --repl road -o "$W/maps/renamed.json"
gst map-pad "$W/maps/renamed.json" -o "$W/maps/padded.json" --margin 1
gst map-diff "$P/levels/causeway.json" "$W/maps/padded.json" --json "$W/reports/map_diff.json"
gst level-curve --kind custom --levels 4 --anchors '1:36,4:90' --csv "$W/reports/level_curve.csv"
gst data-diff data/towers.csv data/towers.csv --key id --json "$W/reports/data_diff.json"

echo "== 4. levels -> Godot: tiles, water colliders, nav, object markers =="
gst map-to-godot "$P/levels/causeway.json" -o "$P/levels/causeway_tiles.tscn" \
  --tileset res://levels/causeway_tileset.tres --write-tileset "$P/levels/causeway_tileset.tres" --res res://art/
gst tile-colliders "$P/levels/causeway.json" --layer ground --solid 3 -o "$W/maps/solid.json"
gst tile-colliders-to-godot "$W/maps/solid.json" -o "$P/levels/causeway_solid.tscn"
gst collider-preview "$W/maps/solid.json" --map "$P/levels/causeway.json" -o "$W/preview/colliders.png" --scale 2
gst nav-to-godot "$P/levels/causeway.json" -o "$P/levels/causeway_nav.tscn" --ground-layer path --no-colliders
gst map-objects-to-godot "$P/levels/causeway.json" -o "$P/levels/causeway_objects.tscn" --res res://art/
gst tile-preview "$P/levels/causeway.json" -o "$W/preview/causeway.png" --scale 2
gst prefab-index "$P/levels" -o "$W/reports/prefabs.csv"

echo "== 5. towers: sprite-stack, outline, shadow, bleed, atlas =="
gst sprite-stack "$W/raw/towers" -o "$W/towers/flat" --layers base,head --anchor center
gst sprite-outline-gen "$W"/towers/flat/*.png -o "$W/towers/line" --mode outer --width 1 --color '#1a241c' --keep-size
gst sprite-shadow "$W"/towers/line/*.png -o "$W/towers/final" --mode contact --keep-size --opacity 0.45
gst alpha-bleed "$W"/towers/final/*.png -o "$W/towers/bleed" --distance 1
gst atlas-pack "$W/towers/bleed" -o "$P/art/towers" --padding 1 --no-trim --no-pot
gst atlas-validate "$P/art/towers.json" --padding 1
gst atlas-to-godot "$P/art/towers.json" -o "$P/art/towers_frames.tres" --per-frame --res res://art/towers.png
gst sprite-scale "$W/towers/bleed/arrow.png" -o "$W/icon/arrow.png" --size 1024x1024
gst icon-gen "$W/icon/arrow.png" -o "$W/icon/set" --bg '#0e1612'
cp "$W/icon/set/web/icon-192.png" "$P/art/icon.png"

echo "== 6. creeps: recolor, rename, outline, shadow, bleed, anim-to-godot =="
mkdir -p "$W/creep/src" "$W/creep/recolor" "$W/creep/body"
cp "$W"/raw/creeps/*.png "$W/creep/src/"
gst sprite-recolor "$W"/creep/src/grub_*.png -o "$W/creep/recolor" --map 6aa84f:e6c84a
gst asset-rename run "$W/creep/recolor" --replace grub=runner --apply --log "$W/reports/rename_log.json"
cp "$W"/creep/src/grub_*.png "$W"/creep/src/brute_*.png "$W"/creep/recolor/runner_*.png "$W/creep/body/"
gst sprite-outline-gen "$W"/creep/body/*.png -o "$W/creep/line" --mode outer --width 1 --color '#1a241c' --keep-size
gst sprite-shadow "$W"/creep/line/*.png -o "$W/creep/shadow" --mode contact --keep-size --opacity 0.45
gst alpha-bleed "$W"/creep/shadow/*.png -o "$W/creep/bleed" --distance 2
cp "$W"/creep/bleed/*.png "$P/art/creeps/"
gst anim-from-folder "$P/art/creeps" -o "$W/creep/clips.json" --pattern '{clip}_{frame}.png' --default-fps 8
gst anim-pingpong "$W/creep/clips.json" -o "$W/creep/ping.json"
gst anim-retarget-fps "$W/creep/ping.json" -o "$W/creep/fps.json" --fps 8
gst anim-to-godot "$W/creep/fps.json" --frames "$P/art/creeps" -o "$P/art/creeps_frames.tres" --res res://art/creeps
cp "$W"/raw/puff/*.png "$P/art/puff/"
gst anim-from-folder "$P/art/puff" -o "$W/creep/puff_clips.json" --pattern '{clip}_{frame}.png' --default-fps 10 --once puff
gst anim-to-godot "$W/creep/puff_clips.json" --frames "$P/art/puff" -o "$P/art/puff_frames.tres" --res res://art/puff
gst anim-hold "$W/creep/puff_clips.json" -o "$W/creep/puff_held.json" --to-duration 0.8
gst pixel-lint "$P"/art/creeps/*.png --json "$W/reports/creep_pixel_lint.json" || true
gst frame-timing-check "$W/creep/fps.json" --strict --report "$W/reports/frame_timing.json"

echo "== 7. title, panel, fonts, localisation =="
gst parallax-preview "$W/raw/parallax/sky.png" "$W/raw/parallax/hills.png" "$W/raw/parallax/reeds.png" \
  -o "$W/preview/title.gif" --speeds 0,0.35,0.9 --width 320 --height 192 --frames 8 --fps 8 \
  --png "$P/art/title_bg.png"
gst particle-preview -o "$W/preview/puff.gif" --width 32 --height 32 --frames 6 --fps 8 --seed 11 --count 12
gst gif-to-frames "$W/preview/puff.gif" -o "$W/preview/puff_frames" --prefix puff
cp "$W/raw/ui/panel.png" "$P/ui/panel.png"
gst nine-slice "$P/ui/panel.png" --insets 6,6,6,6 --preview "$W/preview/panel.png" --sizes 240x120,320x16
gst nine-slice-to-godot "$P/ui/panel.png" -o "$P/ui/panel_style.tres" --insets 6,6,6,6 --res res://ui/
gst loc-check data/loc.csv --max-ratio 5
gst loc-key-lint data/loc.csv --separator _
gst loc-placeholder-lint data/loc.csv
gst loc-stats data/loc.csv --json "$W/reports/loc_stats.json"
gst loc-sort data/loc.csv -o "$W/loc/sorted.csv"
gst loc-split "$W/loc/sorted.csv" -o "$W/loc/split"
gst loc-join "$W/loc/split" -o "$W/loc/joined.csv" --langs en,de,fr
gst loc-missing data/loc.csv
gst loc-plurals data/loc.csv
gst loc-fill data/loc.csv --source en -o "$W/loc/filled.csv"
gst pseudoloc data/loc.csv -o "$W/font/loc_pseudo.csv" --column en --new-column en_XA
python3 - << 'PY'
chars = set()
text = open("data/loc.csv", encoding="utf-8").read()
chars.update(c for c in text if c.isprintable() and not c.isspace())
chars.update("0123456789:+-/x.<>%")
open("work/font/charset.txt", "w", encoding="utf-8").write("".join(sorted(chars)))
PY
gst font-subset data/fonts/DejaVuSans.ttf data/loc.csv "$W/font/charset.txt" -o "$W/font/reed.ttf" --drop-hinting
gst font-check data/loc.csv --font "$W/font/reed.ttf" --ignore _
gst loc-fit data/loc.csv --font "$W/font/reed.ttf" --size 11 --limit-default 300 --max-lines 1 --limits data/loc_limits.csv
gst loc-fit "$W/font/loc_pseudo.csv" --font "$W/font/reed.ttf" --size 11 --limit-default 300 --max-lines 1 \
  --json "$W/reports/pseudo_fit.json" > /dev/null || true
gst text-wrap-bake data/loc.csv -o "$W/font/wrapped.csv" --font "$W/font/reed.ttf" --size 11 --width 300
gst bmfont-gen --font "$W/font/reed.ttf" --size 11 --no-aa --padding 1 --charfile "$W/font/charset.txt" -o "$W/font/reed11"
gst bmfont-gen --font "$W/font/reed.ttf" --size 16 --no-aa --padding 1 --charfile "$W/font/charset.txt" -o "$W/font/reed16"
gst font-check "$W/font/charset.txt" --font "$W/font/reed11.fnt" --font "$W/font/reed16.fnt"
gst font-preview "$W/font/reed.ttf" -o "$W/preview/font.png" --sizes 11,16 --csv data/loc.csv --no-pangram
gst font-to-godot "$W/font/reed11.fnt" -o "$P/ui/reed11_theme.tres" --res res://ui/ --copy-dir "$P/ui"
gst font-to-godot "$W/font/reed16.fnt" -o "$P/ui/reed16_theme.tres" --res res://ui/ --copy-dir "$P/ui"
gst loc-to-godot data/loc.csv -o "$W/loc/loc.csv" --key id --langs en,de,fr --translation-dir "$P/i18n"
gst dialogue-lint data/briefing.yarn
gst dialogue-extract data/briefing.yarn -o "$W/reports/lines.csv"
gst dialogue-stats data/briefing.yarn --json "$W/reports/dialogue_stats.json"
gst dialogue-graph data/briefing.yarn --start Briefing --dot "$W/reports/dialogue.dot" --mermaid "$W/reports/dialogue.mmd" --json "$W/reports/dialogue.json"
gst dialogue-to-yarn "$W/reports/lines.csv" -o "$W/reports/lines.yarn"
gst credits-roll data/credits.txt -o "$W/preview/credits.gif" --width 320 --height 192 --font "$W/font/reed.ttf" --fps 8

echo "== 8. data tables -> Godot resources =="
gst game-data-lint data/schema.json --root data --strict
gst data-to-godot data/towers.csv -o "$P/data/towers.tres" --script "$P/data/towers.gd" --res res://data/
gst data-to-godot data/creeps.csv -o "$P/data/creeps.tres" --script "$P/data/creeps.gd" --res res://data/
gst data-to-godot data/waves.csv -o "$P/data/waves.tres" --script "$P/data/waves.gd" --res res://data/
gst data-to-godot data/build.csv -o "$P/data/build.tres" --script "$P/data/build.gd" --res res://data/

echo "== 9. sfx chain, then the music loop =="
A="$W/audio"
for spec in blip:blip:11:0 place:coin:11:2 shoot:laser:11:-2 hit:hit:11:0 death:explosion:11:0 win:powerup:11:3 leak:jump:11:-5 wave:blip:12:6; do
  IFS=: read -r name preset seed semi <<< "$spec"
  id="$(printf '%04d' "$seed")"
  gst sfx-gen "$preset" -o "$A/gen" -n 1 --seed "$seed"
  gst wav-dc-remove "$A/gen/${preset}_${id}.wav" --outdir "$A/dc"
  gst wav-trim "$A/dc/${preset}_${id}.wav" --outdir "$A/trim" --pad-ms 8
  gst wav-mono "$A/trim/${preset}_${id}.wav" --outdir "$A/mono" --mode mix
  gst wav-resample "$A/mono/${preset}_${id}.wav" --rate 22050 --outdir "$A/rs"
  gst wav-fade "$A/rs/${preset}_${id}.wav" -o "$A/fade/${name}.wav" --in 0.002 --fade-out 0.008
  gst sfx-pitch "$A/fade/${name}.wav" -o "$A/pitch/${name}.wav" --semitones "$semi"
  gst wav-gain "$A/pitch/${name}.wav" --gain -1 --outdir "$A/gain"
  gst wav-limit "$A/gain/${name}.wav" -o "$A/limit/${name}.wav" --ceiling-db -1
done
gst sfx-normalize "$A"/limit/*.wav --outdir "$P/audio/sfx" --peak -3
gst sfx-pitch "$P/audio/sfx/death.wav" -o "$A/music/kick.wav" --semitones -8
gst sfx-pitch "$P/audio/sfx/hit.wav" -o "$A/music/hat.wav" --semitones 6
cp "$P/audio/sfx/blip.wav" "$A/music/blip.wav"
python3 src/make_music.py -o "$A/music/music.json" --blip blip.wav --kick kick.wav --hat hat.wav
gst sfx-mix "$A/music/music.json" -o "$A/music/music_raw.wav"
gst wav-loud-apply "$A/music/music_raw.wav" -o "$A/music/loud" --target -16 --max-true-peak -1
read -r LOOP_START LOOP_END < <(python3 src/make_music.py --span "$A/music/loud/music_raw.wav")
gst loop-xfade "$A/music/loud/music_raw.wav" -o "$A/music/xfade.wav" --start "$LOOP_START" --end "$LOOP_END" --fade-ms 40
gst wav-loop-snap "$A/music/xfade.wav" -o "$P/audio/music.wav" --start "$LOOP_START" --end "$LOOP_END"
gst wav-loop-meta show "$P/audio/music.wav"
gst wav-batch-meta "$P"/audio/sfx/*.wav "$P/audio/music.wav" --csv "$W/reports/audio_meta.csv" --quiet || true
gst cue-sheet "$P"/audio/sfx/*.wav "$P/audio/music.wav" --csv "$W/reports/cue_sheet.csv"
gst sfx-bank pack "$P/audio/sfx" -o "$W/reports/sfx_bank"
gst sfx-spectrogram "$P/audio/music.wav" -o "$W/preview/music_spectrogram.png"
gst audio-tidy "$P"/audio/sfx/*.wav "$P/audio/music.wav" --json "$W/reports/audio_tidy.json"

echo "== 10. import presets, input map, project audits, previews =="
gst godot-import-presets "$P" -r data/import_rules.json --force
gst input-map-lint "$P/project.godot" --scan "$P/scripts" --parity --strict
gst godot-res-lint "$P" --strict
gst asset-unused "$P" --strict --json "$W/reports/asset_unused.json"
gst texture-budget "$P" --fail-over-mb 4 --json "$W/reports/texture_budget.json"
gst asset-lint "$P" -r data/asset_rules.json --json "$W/reports/asset_lint.json"
gst build-report "$P" -r data/asset_rules.json -o "$W/reports/build.md"
gst palette-extract "$P/art/tiles.png" "$P/art/towers.png" -o "$W/preview/palette.png" -n 16
gst colorblind-sim sim "$W/preview/causeway.png" -o "$W/preview/colorblind"
mkdir -p "$W/creep/grub" && cp "$P"/art/creeps/grub_*.png "$W/creep/grub/"
gst onion-skin "$W/creep/grub" -o "$W/preview/grub_onion.png" --loop --scale 4
gst contact-sheet "$W"/towers/bleed/*.png -o "$W/preview/towers_contact.png" --cell 32x32 --columns 3
gst frames-to-sheet "$W/creep/grub" -o "$W/preview/grub_sheet" --columns 4 --no-crop
gst spritesheet-gif "$W/preview/grub_sheet.json" -o "$W/preview/grub.gif" --scale 4
gst asset-manifest build "$P" -o "$W/reports/manifest.json"

if [ "$MODE" = "--verify" ] || [ "$MODE" = "--movie" ]; then
  : "${GODOT_BIN:?GODOT_BIN must point at Godot 4.7+}"
  godot_env
  echo "== 11. Godot headless import =="
  godot_run "$GODOT_BIN" --headless --path "$P" --import --quit > "$W/import.log" 2>&1 || true
  if grep -E "ERROR|SCRIPT ERROR|Failed" "$W/import.log"; then echo "import errors" >&2; exit 1; fi
  echo "import clean ($(wc -l < "$W/import.log") log lines)"
  echo "== 12. autoplay: locales, input check, place towers, survive every wave =="
  SAVE="user://reed_autoplay.json"
  godot_run timeout 180 "$GODOT_BIN" --headless --path "$P" --fixed-fps 60 -- --autoplay "--save=$SAVE" > "$W/autoplay.log" 2>&1 || true
  grep -E "TD_|INPUT_OK|NAV_|TITLE_LOCALE" "$W/autoplay.log" || true
  if grep -E "SCRIPT ERROR|ERROR:|still in use|leaked|TD_FAIL|TD_LEAK|NAV_FAIL" "$W/autoplay.log"; then echo "runtime errors" >&2; exit 1; fi
  grep -q "TD_WIN" "$W/autoplay.log"
  grep -q "TD_DONE" "$W/autoplay.log"
  grep -q "NAV_OK" "$W/autoplay.log"
  grep -q "INPUT_OK true" "$W/autoplay.log"
  echo "== 13. lint the save file the game wrote =="
  mkdir -p "$W/savecheck"
  SAVE_FILE="$(sed -n 's/^TD_DONE .* save=//p' "$W/autoplay.log")"
  cp "$SAVE_FILE" "$W/savecheck/save.json"
  gst game-data-lint data/save_schema.json --root "$W/savecheck" --strict
fi
if [ "$MODE" = "--movie" ]; then
  echo "== 14. software-GL --write-movie (60 fps, same combat step) -> GIF + stills =="
  mkdir -p "$W/movie/gif"
  LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe godot_run timeout 600 xvfb-run -a -s "-screen 0 1280x720x24" \
    "$GODOT_BIN" --path "$P" --display-driver x11 --rendering-driver opengl3 \
    --rendering-method gl_compatibility --resolution 640x384 --fixed-fps 60 \
    --write-movie "$W/movie/gameplay.avi" -- --autoplay "--save=user://reed_movie.json" > "$W/movie.log" 2>&1 || true
  grep -q TD_DONE "$W/movie.log"
  ffmpeg -y -loglevel error -i "$W/movie/gameplay.avi" -vf "fps=6,scale=320:192:flags=neighbor" "$W/movie/gif/f_%04d.png"
  gst frames-to-sheet "$W/movie/gif" -o "$W/movie/gameplay_sheet" --columns 12 --no-crop
  gst spritesheet-gif "$W/movie/gameplay_sheet.json" -o "$W/movie/gameplay_raw.gif" --fps 6
  gst gif-optimize "$W/movie/gameplay_raw.gif" -o "$W/movie/gameplay.gif" --colors 48
  mkdir -p "$HERE/media"
  cp "$W/movie/gameplay.gif" "$HERE/media/gameplay.gif"
  dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$W/movie/gameplay.avi")"
  ffmpeg -y -loglevel error -ss 1.2 -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_title.png"
  ffmpeg -y -loglevel error -ss 8 -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_wave.png"
  ffmpeg -y -loglevel error -ss 18 -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_fight.png"
  ffmpeg -y -loglevel error -sseof -0.4 -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_win.png"
  bytes="$(stat -c%s "$HERE/media/gameplay.gif")"
  if [ "$bytes" -gt 3145728 ]; then echo "gameplay.gif is ${bytes} bytes (over 3 MB)" >&2; exit 1; fi
  echo "movie ${dur}s gif ${bytes} bytes"
  ls -la "$HERE/media"
fi
echo "build.sh: done"
