#!/usr/bin/env bash
# ANNOTATED COPY of examples/sample-topdown/build.sh (gamestudio-tools 2.5.0). Every '# [gst <tool>]' line names
# the kit tool the next command runs and the file(s) it produces. $P = project/, $W = work/ (scratch), $S = work/sprites,
# $A = work/audio. Non-gst lines (python3 src/*.py, cp, Godot) are the sample's own authored steps.
# Ember Crypt: rebuild every generated asset of the top-down sample with gst.
# Authored inputs: src/*.py (procedural pixel drawings, blob rule table, object
# placement, music recipe), data/* (CSV/JSON tables, loc, rules, DejaVu font),
# project/project.godot, project/scenes, project/scripts.
# Generated (wiped and rewritten here): project/{art,levels,ui,audio,data,i18n}
# and work/ (intermediates, reports, previews). Godot steps need GODOT_BIN (4.7+).
#
#   bash build.sh            # assets only
#   bash build.sh --verify   # + headless import, autoplay clear, save-file lint
#   bash build.sh --movie    # + verify + software-GL --write-movie -> media/
#   SEED=7 bash build.sh     # run seed (floors use SEED*100+1, SEED*100+2)
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
SEED="${SEED:-7}"
P="$HERE/project"
W="$HERE/work"
cd "$HERE"

godot_env() {
  local home="${GST_GODOT_HOME:-}"
  if [ -z "$home" ]; then
    home="$(mktemp -d "${TMPDIR:-/tmp}/gst-sample-topdown.XXXXXX")"
    GST_GODOT_HOME="$home"; export GST_GODOT_HOME
    trap 'rm -rf "$GST_GODOT_HOME"' EXIT
  fi
  mkdir -p "$home/.config" "$home/.local/share" "$home/.cache"
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" XDG_CACHE_HOME="$home/.cache"
}

rm -rf "$P/art" "$P/levels" "$P/ui" "$P/audio" "$P/data" "$P/i18n" "$P/.godot" "$W"
mkdir -p "$P/art" "$P/levels" "$P/ui/icons" "$P/audio/sfx" "$P/data" "$P/i18n" \
         "$W/raw" "$W/tiles/props" "$W/maps" "$W/sprites" "$W/audio/sfx" "$W/preview" "$W/reports" "$W/font"
printf '*\n' > "$W/.gdignore"

echo "== 1. tiles: tex-gen -> tileset-gen 47-tile blob sheet; props via lut-tool + frames-to-sheet =="
python3 src/make_art.py -o "$W/raw"
# [gst tex-gen bricks] produces $W/tiles/wall.png
gst tex-gen bricks -o "$W/tiles/wall.png"  --size 16 --seed 11 --count 3 --color-a 5f574f --color-b 83769c --mortar-color 1d2b53
# [gst tex-gen noise] produces $W/tiles/floor.png
gst tex-gen noise  -o "$W/tiles/floor.png" --size 16 --seed 12 --color-a 3b3648 --color-b 312d3d
# [gst tileset-gen] produces $P/art/walls {.png/.json}
gst tileset-gen -o "$P/art/walls" --tile 16 --border 3 --inner "$W/tiles/wall.png" --outer "$W/tiles/floor.png" --edge-color '#1d2b53'
# [gst lut-tool make] produces $W/tiles/shadow_lut.png
gst lut-tool make --size 16 --brightness -0.05 -o "$W/tiles/shadow_lut.png"
cp "$W/tiles/floor.png" "$W/tiles/props/p00_floor.png"
# [gst lut-tool apply] produces $W/tiles/props/p01_shadow.png
gst lut-tool apply "$W/tiles/floor.png" --lut "$W/tiles/shadow_lut.png" -o "$W/tiles/props/p01_shadow.png"
cp "$W/raw/props/p02_stairs.png" "$W/raw/props/p03_rune.png" "$W/tiles/props/"
# [gst frames-to-sheet] produces $P/art/props {.png/.json}
gst frames-to-sheet "$W/tiles/props" -o "$P/art/props" --columns 4 --no-crop
python3 src/blob_rules.py "$P/art/walls.json" -o "$W/tiles/blob_rules.json"
# [gst tile-dedupe] produces $W/reports/walls_dedupe.png
gst tile-dedupe "$P/art/walls.png" --tile 16 -o "$W/reports/walls_dedupe.png"

echo "== 2. levels: dungeon-gen BSP floors + map-blank/map-fill/map-stamp boss arena =="
# [gst dungeon-gen] produces $W/maps/f1 {.txt/.png/.json/_tiles.png}
gst dungeon-gen --mode bsp --size 34x22 --seed $((SEED * 100 + 1)) -o "$W/maps/f1"
# [gst dungeon-gen] produces $W/maps/f2 {.txt/.png/.json/_tiles.png}
gst dungeon-gen --mode bsp --size 34x22 --seed $((SEED * 100 + 2)) -o "$W/maps/f2"
# [gst map-blank] produces $W/maps/boss_blank.json
gst map-blank -o "$W/maps/boss_blank.json" --size 22x14 --tile 16 --layers dungeon \
  --tileset f1_tiles.png --tilecount 2 --columns 2
# [gst map-fill] produces $W/maps/boss_a.json
gst map-fill "$W/maps/boss_blank.json" -o "$W/maps/boss_a.json" --layer dungeon --gid 2 --rect 0,0,22,14
# [gst map-fill] produces $W/maps/boss_b.json
gst map-fill "$W/maps/boss_a.json" -o "$W/maps/boss_b.json" --layer dungeon --gid 1 --rect 1,1,20,12
# [gst map-blank] produces $W/maps/pillar.json
gst map-blank -o "$W/maps/pillar.json" --size 2x2 --tile 16 --layers dungeon --tileset f1_tiles.png --tilecount 2 --columns 2
# [gst map-fill] produces $W/maps/pillar2.json
gst map-fill "$W/maps/pillar.json" -o "$W/maps/pillar2.json" --layer dungeon --gid 2 --rect 0,0,2,2
cp "$W/maps/boss_b.json" "$W/maps/boss_raw.json"
for at in 5,4 15,4 5,8 15,8; do
  # [gst map-stamp] produces $W/maps/boss_tmp.json
  gst map-stamp "$W/maps/boss_raw.json" --prefab "$W/maps/pillar2.json" --at "$at" --layer dungeon \
    -o "$W/maps/boss_tmp.json" --tiles-only
  mv "$W/maps/boss_tmp.json" "$W/maps/boss_raw.json"
done
cp "$W/maps/boss_raw.json" "$W/maps/f3.json"
for n in 1 2 3; do
  # [gst map-auto-layer] produces $W/maps/f${n}_walls.json
  gst map-auto-layer "$W/maps/f$n.json" --rules "$W/tiles/blob_rules.json" -o "$W/maps/f${n}_walls.json"
  # [gst map-auto-layer] produces $W/maps/f${n}_auto.json
  gst map-auto-layer "$W/maps/f${n}_walls.json" --rules data/floor_rules.json -o "$W/maps/f${n}_auto.json"
done
python3 src/compose.py "$W/maps/f1_auto.json" -o "$P/levels/floor1.json" --mode floor --floor 1 --seed "$SEED" --name "Floor 1"
python3 src/compose.py "$W/maps/f2_auto.json" -o "$P/levels/floor2.json" --mode floor --floor 2 --seed "$SEED" --name "Floor 2"
python3 src/compose.py "$W/maps/f3_auto.json" -o "$P/levels/boss.json"   --mode boss  --floor 3 --seed "$SEED" --name "Boss"

echo "== 3. level checks: paths, reachability, props, budget, stats =="
for L in floor1 floor2; do
  # [gst map-path] report $W/preview/${L}_path_key.png, $W/reports/${L}_path_key.json
  gst map-path "$P/levels/$L.json" --start-name spawn --goal-name key --solid-layer walls --fail-if-none \
    --png "$W/preview/${L}_path_key.png" --scale 4 --json "$W/reports/${L}_path_key.json"
  # [gst map-path] report $W/reports/${L}_path_stairs.json
  gst map-path "$P/levels/$L.json" --start-name key --goal-name stairs --solid-layer walls --fail-if-none \
    --json "$W/reports/${L}_path_stairs.json"
  # [gst map-reach] report $W/reports/${L}_reach.json
  gst map-reach "$P/levels/$L.json" --start-name spawn --solid-layer walls --require key,stairs,enemy --adjacent \
    --json "$W/reports/${L}_reach.json"
done
# [gst map-reach] report $W/reports/boss_reach.json
gst map-reach "$P/levels/boss.json" --start-name spawn --solid-layer walls --require enemy,portal,heart --adjacent \
  --json "$W/reports/boss_reach.json"
# [gst tmx-props-lint] report $W/reports/props.md
gst tmx-props-lint "$P"/levels/*.json --schema data/map_props.schema.json --md "$W/reports/props.md"
# [gst level-budget] report $W/reports/budget.md
gst level-budget "$P"/levels/*.json --budget data/level_budget.json --fail-on-under --md "$W/reports/budget.md"
# [gst tilemap-stats] report $W/reports/tilemap_stats.csv
gst tilemap-stats "$P"/levels/*.json --fail-on-empty-layer --csv "$W/reports/tilemap_stats.csv"
# [gst tmx-objects-csv] produces $W/reports/objects.csv
gst tmx-objects-csv "$P"/levels/*.json -o "$W/reports/objects.csv"
for L in floor1 floor2 boss; do
  # [gst tmx-gid-usage] report $W/reports/${L}_gid_usage.json
  gst tmx-gid-usage "$P/levels/$L.json" --json "$W/reports/${L}_gid_usage.json" --fail-on-unused-tileset
done

echo "== 4. levels -> Godot: TileMapLayer + TileSet, colliders, navigation, object markers =="
for L in floor1 floor2 boss; do
  M="$P/levels/$L"
  # [gst map-to-godot] produces ${M}_tiles.tscn, ${M}_tileset.tres; report $W/maps/${L}_cells.json
  gst map-to-godot "$M.json" -o "${M}_tiles.tscn" --tileset "res://levels/${L}_tileset.tres" \
    --write-tileset "${M}_tileset.tres" --res res://art/ --cells-json "$W/maps/${L}_cells.json"
  # [gst tile-colliders] produces $W/maps/${L}_solid.json
  gst tile-colliders "$M.json" --layer walls -o "$W/maps/${L}_solid.json"
  # [gst tile-colliders-to-godot] produces ${M}_solid.tscn
  gst tile-colliders-to-godot "$W/maps/${L}_solid.json" -o "${M}_solid.tscn"
  # [gst nav-to-godot] produces ${M}_nav.tscn
  gst nav-to-godot "$M.json" -o "${M}_nav.tscn" --solid-layer walls --no-colliders
  # [gst map-objects-to-godot] produces ${M}_objects.tscn
  gst map-objects-to-godot "$M.json" -o "${M}_objects.tscn" --res res://art/
  # [gst tile-preview] produces $W/preview/$L.png
  gst tile-preview "$M.json" -o "$W/preview/$L.png" --objects --scale 1
done

echo "== 5. actors: team-outline / palette-swap variants, asset-rename, scale, palette, outline, shadow, atlas =="
S="$W/sprites"
mkdir -p "$S/var" "$S/all" "$S/pal" "$S/line" "$S/final" "$S/slash" "$S/pk_pal" "$S/pk_final" "$S/icons" "$S/misc"
# [gst team-outline] produces $S/var
gst team-outline "$W"/raw/sprites/bat-fly_*.png -o "$S/var" --team red=#ff004d --key '#7e2553'
# [gst palette-swap] produces $S/var
gst palette-swap "$W"/raw/sprites/wizard-*.png -o "$S/var" --hue 180
# [gst asset-rename run] produces renamed files in place (dry run without --apply); report $W/reports/rename_log.json
gst asset-rename run "$S/var" --replace bat-fly=batred-fly --replace _red= --replace wizard=warlock --replace _swap= \
  --apply --log "$W/reports/rename_log.json"
cp "$W"/raw/sprites/*.png "$S/var"/*.png "$S/all/"
# [gst sprite-scale] produces $S/all
gst sprite-scale "$W"/raw/boss/*.png -o "$S/all" --scale 2
# [gst palette-apply] produces $S/pal
gst palette-apply "$S"/all/*.png -o "$S/pal" --palette pico8
# [gst sprite-outline-gen] produces $S/line
gst sprite-outline-gen "$S"/pal/*.png -o "$S/line" --mode outer --width 1 --color '#1d2b53' --keep-size
# [gst sprite-shadow] produces $S/final
gst sprite-shadow "$S"/line/*.png -o "$S/final" --mode contact --keep-size --opacity 0.45
# [gst pixel-lint] report $W/reports/actors_pixel_lint.json
gst pixel-lint "$S"/final/*.png --json "$W/reports/actors_pixel_lint.json" || true
# [gst anim-from-folder] produces $S/clips.json
gst anim-from-folder "$S/final" -o "$S/clips.json" --pattern '{clip}_{frame}.png' --default-fps 8 \
  --fps 'player-walk-*=10,boss-charge=12' --once 'player-idle-*'
# [gst atlas-pack] produces $P/art/actors {.png/.json}
gst atlas-pack "$S/final" -o "$P/art/actors" --padding 1 --no-pot
# [gst atlas-validate] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst atlas-validate "$P/art/actors.json" --padding 1
# [gst atlas-to-godot] produces $P/art/actors_frames.tres
gst atlas-to-godot "$P/art/actors.json" -o "$P/art/actors_frames.tres" --clips "$S/clips.json" --res res://art/actors.png
# [gst hitbox-gen] produces $S/hitboxes.json
gst hitbox-gen --atlas "$P/art/actors.json" -o "$S/hitboxes.json"
# [gst hitbox-to-godot] produces $P/art/actors_hitboxes.tscn
gst hitbox-to-godot "$S/hitboxes.json" -o "$P/art/actors_hitboxes.tscn" --shape aabb
# [gst palette-apply] produces $S/slash
gst palette-apply "$W/raw/slash.png" -o "$S/slash" --palette pico8
# [gst sprite-angles] produces $P/art/slash.png
gst sprite-angles "$S/slash/slash.png" -o "$P/art/slash.png" --angles 8 --prefix slash
# [gst atlas-to-godot] produces $P/art/slash_frames.tres
gst atlas-to-godot "$P/art/slash.json" -o "$P/art/slash_frames.tres" --per-frame --res res://art/slash.png

echo "== 6. pickups, HUD icons, portal, title backdrop, app icon =="
# [gst palette-apply] produces $S/pk_pal
gst palette-apply "$W"/raw/pickups/*.png -o "$S/pk_pal" --palette pico8
# [gst sprite-outline-gen] produces $S/pk_final
gst sprite-outline-gen "$S"/pk_pal/*.png -o "$S/pk_final" --mode outer --width 1 --color '#1d2b53' --keep-size
# [gst anim-from-folder] produces $S/pk_clips.json
gst anim-from-folder "$S/pk_final" -o "$S/pk_clips.json" --pattern '{clip}_{frame}.png' --default-fps 8 --once heart-idle,key-idle
# [gst atlas-pack] produces $P/art/pickups {.png/.json}
gst atlas-pack "$S/pk_final" -o "$P/art/pickups" --padding 1 --no-pot
# [gst atlas-validate] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst atlas-validate "$P/art/pickups.json" --padding 1
# [gst atlas-to-godot] produces $P/art/pickups_frames.tres
gst atlas-to-godot "$P/art/pickups.json" -o "$P/art/pickups_frames.tres" --clips "$S/pk_clips.json" --res res://art/pickups.png
# [gst atlas-unpack] produces $S/icons
gst atlas-unpack "$P/art/pickups.json" -o "$S/icons" --untrim
cp "$S/icons/heart-idle_0.png" "$S/icons/coin-spin_0.png" "$S/icons/key-idle_0.png" "$P/ui/icons/"
# [gst sprite-scale] produces $S/misc
gst sprite-scale "$W/raw/props/p03_rune.png" -o "$S/misc" --scale 2
# [gst palette-swap] produces $S/misc
gst palette-swap "$S/misc/p03_rune.png" -o "$S/misc" --hue 200
cp "$S/misc/p03_rune_swap.png" "$P/art/portal.png"
# [gst tile-preview] produces $S/misc/floor1_clean.png
gst tile-preview "$P/levels/floor1.json" -o "$S/misc/floor1_clean.png" --scale 1
# [gst sprite-canvas] produces $S/misc/crop
gst sprite-canvas "$S/misc/floor1_clean.png" -o "$S/misc/crop" --size 320x180 --anchor center
# [gst lut-tool make] produces $S/misc/title_lut.png
gst lut-tool make --size 16 --brightness -0.18 --saturation 0.6 -o "$S/misc/title_lut.png"
# [gst lut-tool apply] produces $P/art/title_bg.png
gst lut-tool apply "$S/misc/crop/floor1_clean.png" --lut "$S/misc/title_lut.png" -o "$P/art/title_bg.png"
# [gst sprite-scale] produces $S/icon_master
gst sprite-scale "$S/final/player-idle-down_0.png" -o "$S/icon_master" --size 1024x1024
# [gst icon-gen] produces $S/icon
gst icon-gen "$S/icon_master/player-idle-down_0.png" -o "$S/icon" --bg '#1d2b53'
cp "$S/icon/web/icon-192.png" "$P/art/icon.png"

echo "== 7. UI + localisation: loc lints, font subset -> bmfont-gen -> font-to-godot, nine-slice, loc-to-godot =="
# [gst loc-check] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst loc-check data/loc.csv --max-ratio 5
# [gst loc-key-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst loc-key-lint data/loc.csv --separator _
# [gst loc-placeholder-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst loc-placeholder-lint data/loc.csv
# [gst loc-stats] report $W/reports/loc_stats.json
gst loc-stats data/loc.csv --json "$W/reports/loc_stats.json"
# [gst pseudoloc] produces $W/font/loc_pseudo.csv
gst pseudoloc data/loc.csv -o "$W/font/loc_pseudo.csv" --column en --new-column en_XA
# glyph set: every translated string plus HUD digits/symbols and upper-case locale codes
{ cut -d, -f2- data/loc.csv | tail -n +2 | tr -d ',\n'; printf ',0123456789:+-/x.<>%%ABCDEFGHIJKLMNOPQRSTUVWXYZ'; } > "$W/font/charset.txt"
# [gst font-subset] produces $W/font/ember.ttf
gst font-subset data/fonts/DejaVuSans.ttf -o "$W/font/ember.ttf" --drop-hinting --chars "$(cat "$W/font/charset.txt")"
# [gst font-check] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst font-check data/loc.csv --font "$W/font/ember.ttf" --ignore _
# [gst loc-fit] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst loc-fit data/loc.csv --font "$W/font/ember.ttf" --size 11 --limit-default 300 --max-lines 1
# [gst loc-fit] report $W/reports/pseudo_fit.json
gst loc-fit "$W/font/loc_pseudo.csv" --font "$W/font/ember.ttf" --size 11 --limit-default 300 --max-lines 1 \
  --json "$W/reports/pseudo_fit.json" > /dev/null || true
# [gst bmfont-gen] produces $W/font/ember11 {.fnt/.png}
gst bmfont-gen --font "$W/font/ember.ttf" --size 11 --no-aa --padding 1 --charfile "$W/font/charset.txt" -o "$W/font/ember11"
# [gst bmfont-gen] produces $W/font/ember22 {.fnt/.png}
gst bmfont-gen --font "$W/font/ember.ttf" --size 22 --padding 1 --charfile "$W/font/charset.txt" -o "$W/font/ember22"
# [gst font-check] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst font-check "$W/font/charset.txt" --font "$W/font/ember11.fnt" --font "$W/font/ember22.fnt"
# [gst font-preview] produces $W/preview/font.png; report data/loc.csv
gst font-preview "$W/font/ember.ttf" -o "$W/preview/font.png" --sizes 11,22 --csv data/loc.csv --no-pangram
# [gst font-to-godot] produces $P/ui/ember11_theme.tres; report $P/ui
gst font-to-godot "$W/font/ember11.fnt" -o "$P/ui/ember11_theme.tres" --res res://ui/ --copy-dir "$P/ui"
# [gst font-to-godot] produces $P/ui/ember22_theme.tres; report $P/ui
gst font-to-godot "$W/font/ember22.fnt" -o "$P/ui/ember22_theme.tres" --res res://ui/ --copy-dir "$P/ui"
cp "$W/raw/ui/panel.png" "$P/ui/panel.png"
# [gst nine-slice] report $W/preview/panel.png
gst nine-slice "$P/ui/panel.png" --insets 6,6,6,6 --preview "$W/preview/panel.png" --sizes 316x20,120x40
# [gst nine-slice-to-godot] produces $P/ui/panel_style.tres
gst nine-slice-to-godot "$P/ui/panel.png" -o "$P/ui/panel_style.tres" --insets 6,6,6,6 --res res://ui/
# [gst loc-to-godot] produces $W/loc.csv, $P/i18n
gst loc-to-godot data/loc.csv -o "$W/loc.csv" --key id --langs en,de,fr --translation-dir "$P/i18n"

echo "== 8. data: schema lint, loot simulation, enemy table -> Godot Resource =="
# [gst game-data-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst game-data-lint data/schema.json --root data --strict
# [gst drop-sim] report $W/reports/drop_sim.json
gst drop-sim data/loot.json --trials 20000 --seed 1 --expect common:coin:0.45:0.55 --expect boss:coin:1:1 \
  --json "$W/reports/drop_sim.json"
# [gst data-to-godot] produces $P/data/enemies.tres, $P/data/enemies.gd
gst data-to-godot data/enemies.csv -o "$P/data/enemies.tres" --script "$P/data/enemies.gd" --res res://data/
cp data/loot.json "$P/data/loot.json"

echo "== 9. audio: sfx-gen one-shots -> pitch/variants/envelope/reverse/mix -> normalize; music via sfx-mix =="
A="$W/audio"
# [gst sfx-gen $k] produces $A/gen
for k in blip coin hit laser explosion powerup; do gst sfx-gen "$k" -o "$A/gen" -n 1 --seed 7; done
for k in blip coin hit laser explosion powerup; do cp "$A/gen/${k}_0007.wav" "$A/$k.wav"; done
# [gst sfx-pitch] produces $A/swing_p.wav
gst sfx-pitch "$A/laser.wav" -o "$A/swing_p.wav" --semitones -5
# [gst sfx-envelope] produces $A/env
gst sfx-envelope "$A/swing_p.wav" -o "$A/env" --attack-ms 4 --decay-ms 60 --sustain 0.3 --release-ms 60
# [gst sfx-variants] produces $A/hitvar
gst sfx-variants "$A/hit.wav" -o "$A/hitvar" -n 3 --seed 3 --semitones 2 --gain-db 1.5
# [gst sfx-pitch] produces $A/hurt.wav
gst sfx-pitch "$A/hit.wav" -o "$A/hurt.wav" --semitones -6
# [gst sfx-reverse] produces $A/stairs.wav
gst sfx-reverse "$A/powerup.wav" -o "$A/stairs.wav"
cp data/roar_recipe.json "$A/roar.json"
# [gst sfx-mix] produces $A/roar.wav
gst sfx-mix "$A/roar.json" -o "$A/roar.wav"
cp "$A/env/"*.wav "$A/swing.wav"
i=0; for f in "$A"/hitvar/*.wav; do cp "$f" "$A/hit_$i.wav"; i=$((i + 1)); done
mkdir -p "$A/game"
for pair in swing:swing hit_0:hit_0 hit_1:hit_1 hit_2:hit_2 hurt:hurt coin:coin pickup:powerup \
            shoot:laser death:explosion roar:roar stairs:stairs blip:blip; do
  cp "$A/${pair#*:}.wav" "$A/game/${pair%%:*}.wav"
done
# [gst sfx-normalize] produces $P/audio/sfx
gst sfx-normalize "$A"/game/*.wav --outdir "$P/audio/sfx" --peak -3
# music: kick and hat from the one-shots, recipe from src/make_music.py, loudness then exact loop
# [gst sfx-pitch] produces $A/kick0.wav
gst sfx-pitch "$A/explosion.wav" -o "$A/kick0.wav" --semitones -7
# [gst wav-loop-snap] produces $A/kick1.wav
gst wav-loop-snap "$A/kick0.wav" -o "$A/kick1.wav" --start 0 --end 6614 --no-meta
# [gst wav-fade] produces $A/kick.wav
gst wav-fade "$A/kick1.wav" -o "$A/kick.wav" --fade-out 0.09
# [gst sfx-pitch] produces $A/hat.wav
gst sfx-pitch "$A/hit.wav" -o "$A/hat.wav" --semitones 5
python3 src/make_music.py -o "$A/music.json" --blip blip.wav --kick kick.wav --hat hat.wav
# [gst sfx-mix] produces $A/music_raw.wav
gst sfx-mix "$A/music.json" -o "$A/music_raw.wav" > "$W/reports/music_mix.txt"; tail -2 "$W/reports/music_mix.txt"
# [gst wav-loud-apply] produces $A/loud
gst wav-loud-apply "$A/music_raw.wav" -o "$A/loud" --target -16 --max-true-peak -1
# [gst wav-loop-snap] produces $P/audio/music.wav
gst wav-loop-snap "$A/loud/music_raw.wav" -o "$P/audio/music.wav" --start 0 --end 705599
# [gst wav-loop-meta show] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst wav-loop-meta show "$P/audio/music.wav"
# [gst wav-batch-meta] report $W/reports/audio_meta.csv
gst wav-batch-meta "$P"/audio/sfx/*.wav "$P/audio/music.wav" --csv "$W/reports/audio_meta.csv" --quiet || true
# [gst cue-sheet] report $W/reports/cue_sheet.csv
gst cue-sheet "$P"/audio/sfx/*.wav "$P/audio/music.wav" --csv "$W/reports/cue_sheet.csv"
# [gst sfx-bank pack] produces $W/reports/sfx_bank
gst sfx-bank pack "$P/audio/sfx" -o "$W/reports/sfx_bank"
# [gst sfx-spectrogram] produces $W/preview/music_spectrogram.png
gst sfx-spectrogram "$P/audio/music.wav" -o "$W/preview/music_spectrogram.png"

echo "== 10. Godot import presets, input map, project audits, previews =="
# [gst godot-import-presets] produces <project>/*.import files
gst godot-import-presets "$P" -r data/import_rules.json --force
# [gst input-map-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst input-map-lint "$P/project.godot" --scan "$P/scripts" --parity --strict
# [gst godot-res-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
gst godot-res-lint "$P" --strict
# [gst asset-unused] report $W/reports/asset_unused.json
gst asset-unused "$P" --strict --json "$W/reports/asset_unused.json"
# [gst texture-budget] report $W/reports/texture_budget.json
gst texture-budget "$P" --fail-over-mb 4 --json "$W/reports/texture_budget.json"
# [gst frame-timing-check] report $W/reports/frame_timing.json
gst frame-timing-check "$S/clips.json" --strict --report "$W/reports/frame_timing.json"
# [gst palette-extract] produces $W/preview/palette.png
gst palette-extract "$P/art/actors.png" "$P/art/walls.png" -o "$W/preview/palette.png" -n 16
# [gst colorblind-sim sim] produces $W/preview/colorblind
gst colorblind-sim sim "$W/preview/floor1.png" -o "$W/preview/colorblind"
mkdir -p "$S/walk_down" && cp "$S"/final/player-walk-down_*.png "$S/walk_down/"
# [gst onion-skin] produces $W/preview/player_onion.png
gst onion-skin "$S/walk_down" -o "$W/preview/player_onion.png" --loop --scale 4
# [gst contact-sheet] produces $W/preview/actors_contact.png
gst contact-sheet "$S"/final/*.png -o "$W/preview/actors_contact.png" --cell 48x48 --columns 10
# [gst spritesheet-gif] produces $W/preview/boss.gif
gst spritesheet-gif "$P/art/actors.json" --clips "$S/clips.json" --clip boss-charge -o "$W/preview/boss.gif" --scale 4 --bg '#1d2b53'
# [gst asset-manifest build] produces $W/reports/manifest.json
gst asset-manifest build "$P" -o "$W/reports/manifest.json"

if [ "$MODE" = "--verify" ] || [ "$MODE" = "--movie" ]; then
  : "${GODOT_BIN:?GODOT_BIN must point at Godot 4.7+}"
  godot_env
  echo "== 11. Godot headless import =="
  "$GODOT_BIN" --headless --path "$P" --import --quit > "$W/import.log" 2>&1 || true
  if grep -E "ERROR|SCRIPT ERROR|Failed" "$W/import.log"; then echo "import errors" >&2; exit 1; fi
  echo "import clean ($(wc -l < "$W/import.log") log lines)"
  echo "== 12. autoplay: seeded run, title locales, input check, 2 floors + boss, save/load =="
  SAVE="user://ember_autoplay.json"
  timeout 300 "$GODOT_BIN" --headless --path "$P" --fixed-fps 60 -- --autoplay "--save=$SAVE" > "$W/autoplay.log" 2>&1 || true
  grep -E "TOPDOWN_|INPUT_OK|LEVEL |SAVE_OK|LOAD_OK|BOSS_DEAD" "$W/autoplay.log"
  if grep -E "SCRIPT ERROR|ERROR:|still in use|leaked" "$W/autoplay.log"; then echo "runtime errors" >&2; exit 1; fi
  grep -q "TOPDOWN_DONE" "$W/autoplay.log" && grep -q "BOSS_DEAD" "$W/autoplay.log" && grep -q "LOAD_OK floor=3" "$W/autoplay.log"
  echo "== 13. lint the save file the game wrote against data/save_schema.json =="
  mkdir -p "$W/savecheck"
  SAVE_FILE="$(sed -n 's/^TOPDOWN_DONE .* save=//p' "$W/autoplay.log")"
  cp "$SAVE_FILE" "$W/savecheck/save.json"
  # [gst game-data-lint] check/inspect only: no asset written, a non-zero exit stops the build (set -e)
  gst game-data-lint data/save_schema.json --root "$W/savecheck" --strict
fi
if [ "$MODE" = "--movie" ]; then
  echo "== 14. software-GL --write-movie (30 fps) -> MP4 + GIF + stills in media/ =="
  mkdir -p "$W/movie"
  LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe timeout 900 xvfb-run -a -s "-screen 0 1280x720x24" \
    "$GODOT_BIN" --path "$P" --display-driver x11 --rendering-driver opengl3 \
    --rendering-method gl_compatibility --resolution 640x360 --fixed-fps 30 \
    --write-movie "$W/movie/gameplay.avi" -- --autoplay "--save=user://ember_movie.json" > "$W/movie.log" 2>&1 || true
  grep -q TOPDOWN_DONE "$W/movie.log"
  ffmpeg -y -loglevel error -i "$W/movie/gameplay.avi" -vf "scale=640:360:flags=neighbor" -c:v libx264 -preset slow -tune animation -pix_fmt yuv420p -crf 32 -c:a aac -b:a 64k "$W/movie/gameplay.mp4"
  rm -rf "$W/movie/gif" && mkdir -p "$W/movie/gif"
  # GIF: 35 s of highlights (title + floor 1, floor 2, boss + win) at 5 fps; the MP4 has the whole run
  ffmpeg -y -loglevel error -i "$W/movie/gameplay.avi" -vsync vfr \
    -vf "fps=5,select='between(t\,0\,14)+between(t\,36\,44)+between(t\,61\,74)',scale=320:-1:flags=neighbor" \
    "$W/movie/gif/f_%04d.png"
  # [gst frames-to-sheet] produces $W/movie/gameplay_sheet {.png/.json}
  gst frames-to-sheet "$W/movie/gif" -o "$W/movie/gameplay_sheet" --columns 24 --no-crop
  # [gst spritesheet-gif] produces $W/movie/gameplay_raw.gif
  gst spritesheet-gif "$W/movie/gameplay_sheet.json" -o "$W/movie/gameplay_raw.gif" --fps 5
  # [gst gif-optimize] produces $W/movie/gameplay.gif
  gst gif-optimize "$W/movie/gameplay_raw.gif" -o "$W/movie/gameplay.gif" --colors 48
  rm -rf "$W/movie/gif" "$W/movie/gameplay_sheet.png" "$W/movie/gameplay_raw.gif"
  mkdir -p "$HERE/media"
  cp "$W/movie/gameplay.gif" "$W/movie/gameplay.mp4" "$HERE/media/"
  dur="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$W/movie/gameplay.avi")"
  for shot in title:1.0 floor1:6.0 floor2:40.0 boss:66.0; do
    ffmpeg -y -loglevel error -ss "${shot#*:}" -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_${shot%%:*}.png"
  done
  ffmpeg -y -loglevel error -sseof -1.5 -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_win.png"
  echo "movie ${dur}s"; grep -E "TOPDOWN_(WIN|DONE)" "$W/movie.log"
  ls -la "$HERE/media"
fi
echo "build.sh: done"
