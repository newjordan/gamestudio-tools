#!/usr/bin/env bash
# Gem Runner: rebuild every generated asset of the sample game with gst.
# Authored inputs: src/*.py (procedural art + level layout), data/*.csv,
# data/import_rules.json, project/project.godot, project/scenes, project/scripts.
# Generated (wiped and rewritten here): project/{art,levels,ui,audio,data,i18n}
# and work/ (intermediates, previews). Requires gst (on PATH or two directories
# above this script). Godot steps run only when GODOT_BIN points at Godot 4.7+.
#
#   bash build.sh            # assets only
#   bash build.sh --verify   # + headless import and the autoplay test
#   bash build.sh --movie    # + verify + 26 s software-GL movie -> work/movie/
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
  local home="${GST_GODOT_HOME:-}"
  if [ -z "$home" ]; then
    home="$(mktemp -d "${TMPDIR:-/tmp}/gst-sample-game.XXXXXX")"
    GST_GODOT_HOME="$home"; export GST_GODOT_HOME
  fi
  mkdir -p "$home/.config" "$home/.local/share" "$home/.cache"
  export HOME="$home" XDG_CONFIG_HOME="$home/.config" XDG_DATA_HOME="$home/.local/share" XDG_CACHE_HOME="$home/.cache"
}

rm -rf "$P/art" "$P/levels" "$P/ui" "$P/audio" "$P/data" "$P/i18n" "$P/.godot" "$W"
mkdir -p "$P/art" "$P/levels" "$P/ui" "$P/audio/sfx" "$P/data" "$P/i18n" \
         "$W/tiles" "$W/maps" "$W/audio" "$W/preview"
printf '*\n' > "$W/.gdignore"

echo "== 1. tiles: tex-gen + own pieces -> frames-to-sheet =="
gst tex-gen noise  -o "$W/tiles/t00_grass.png" --size 16 --seed 3 --color-a 4aaa3a --color-b 2e7a28
gst tex-gen noise  -o "$W/tiles/t01_dirt.png"  --size 16 --seed 4 --color-a 8a6234 --color-b 6a4522
gst tex-gen bricks -o "$W/tiles/t02_brick.png" --size 16 --seed 5 --count 4 --color-a 6c6f8a --color-b 50536e --mortar-color 2a2b3c
gst tex-gen planks -o "$W/tiles/t03_plank.png" --size 16 --seed 6 --count 2 --color-a b0793e --color-b 8a5a2a
python3 src/make_tiles.py -o "$W/tiles"            # edge, gem x4, door x2, torch, panel
mv "$W/tiles/panel.png" "$P/ui/panel.png"
gst frames-to-sheet "$W/tiles" -o "$P/art/tiles" --columns 4 --no-crop

echo "== 2. levels: map-blank -> bake -> jump-arc check =="
gst map-blank -o "$W/maps/blank.json" --size 50x12 --tile 16 --layers ground,platforms,navstrip \
  --tileset ../art/tiles.png --tilecount 12 --columns 4 --pretty
for n in 1 2 3; do
  python3 src/bake_levels.py "$W/maps/blank.json" --level "$n" -o "$P/levels/level$n.json"
  mv "$P/levels/level$n.gaps.json" "$W/maps/level$n.gaps.json"
done
python3 - "$W" "$P" << 'PY'
import json, os, subprocess, sys
w, p = sys.argv[1:3]
gst = os.path.join(os.environ.get("GST_ROOT", ""), "gst")
for n in (1, 2, 3):
    meta = json.load(open(f"{w}/maps/level{n}.gaps.json"))
    for i, g in enumerate(meta["gaps"], 1):
        out = f"{w}/maps/level{n}_gap{i}"
        subprocess.check_call([sys.executable, gst, "jump-arc", f"{p}/levels/level{n}.json", "-o", out + ".png",
            "--start", "%d,%d" % tuple(g["takeoff"]), "--jump-v", str(meta["jump_v"]), "--speed", str(meta["speed"]),
            "--gravity", str(meta["gravity"]), "--solid-layer", "ground", "--json", out + ".json"],
            stdout=subprocess.DEVNULL)
        r = json.load(open(out + ".json"))
        ex = r["end"][0]
        ok = r["landed"] and not r.get("out_of_bounds") and g["land_min"] <= ex <= g["land_max"]
        print(f"level {n} gap {i}: lands at x={ex:.1f} (needs {g['land_min']}..{g['land_max']}) {'OK' if ok else 'FAIL'}")
        if not ok:
            sys.exit(f"level {n} gap {i} is not jumpable with the game's physics")
PY

echo "== 3. levels -> Godot: tiles, colliders, one-way, navmesh, objects =="
for n in 1 2 3; do
  L="$P/levels/level$n"
  gst map-to-godot "$L.json" -o "${L}_tiles.tscn" --tileset "res://levels/level${n}_tileset.tres" \
    --write-tileset "${L}_tileset.tres" --res res://art/ --cells-json "$W/maps/level${n}_cells.json"
  gst tile-colliders "$L.json" --layer ground -o "$W/maps/level${n}_solid.json"
  gst tile-colliders-to-godot "$W/maps/level${n}_solid.json" -o "${L}_solid.tscn"
  gst tile-colliders "$L.json" --layer platforms -o "$W/maps/level${n}_oneway.json"
  gst tile-colliders-to-godot "$W/maps/level${n}_oneway.json" -o "${L}_oneway.tscn"
  gst nav-to-godot "$L.json" -o "${L}_nav.tscn" --solid-layer ground --ground-layer navstrip --no-colliders
  gst map-objects-to-godot "$L.json" -o "${L}_objects.tscn" --res res://art/
  gst tile-preview "$L.json" -o "$W/preview/level${n}.png" --objects --scale 1
done

echo "== 4. characters: own .aseprite -> ase-to-godot, hitbox-gen -> hitbox-to-godot =="
python3 src/make_ase.py -o "$W"
for c in player slime; do
  gst ase-decode "$W/$c.aseprite" -o "$W/${c}_decoded" --no-png --json "$W/$c.ase.json"
  gst ase-to-godot "$W/$c.aseprite" -o "$P/art/$c.tres" --res "res://art/${c}_frames"
  gst hitbox-gen "$P/art/${c}_frames/"*.png -o "$W/${c}_hitbox.json" --pad 0
  gst hitbox-to-godot "$W/${c}_hitbox.json" -o "$P/art/${c}_hitbox.tscn" --shape aabb
  gst frames-to-sheet "$P/art/${c}_frames" -o "$W/preview/${c}_sheet" --columns 9 --no-crop
done

echo "== 5. UI: nine-slice panel, bitmap font, theme =="
gst nine-slice "$P/ui/panel.png" --insets 6,6,6,6 --preview "$W/preview/panel_preview.png" --sizes 48x24,160x40,220x90
gst nine-slice-to-godot "$P/ui/panel.png" -o "$P/ui/panel.tres" --insets 6,6,6,6 --res res://ui/
gst bmfont-gen --font data/fonts/DejaVuSans-subset.ttf --size 11 --no-aa --padding 1 -o "$W/font"
gst font-check --font "$W/font.fnt" data/loc.csv
gst font-to-godot "$W/font.fnt" -o "$P/ui/theme.tres" --res res://ui/ --copy-dir "$P/ui"

echo "== 6. data: translations (2 locales) and enemy stats Resource =="
gst loc-check data/loc.csv 2>/dev/null || true
gst loc-to-godot data/loc.csv -o "$W/strings.csv" --key id --langs en,de --translation-dir "$P/i18n"
gst data-to-godot data/enemies.csv -o "$P/data/enemies.tres" --script "$P/data/enemies.gd" --res res://data/

echo "== 7. audio: kit sample song + loop points, generated sfx =="
cp data/song_loop.wav "$W/audio/music.wav"            # copy of the kit sample samples/loops/song_loop.wav
gst loop-finder "$W/audio/music.wav" --json "$W/audio/music_loop.json"
gst wav-loop-meta from-json "$W/audio/music_loop.json" --dir "$W/audio" -o "$P/audio"
gst wav-loop-meta show "$P/audio/music.wav"
for k in jump coin hit; do gst sfx-gen "$k" -o "$W/audio/sfx" -n 1 --seed 7; done
for k in jump coin hit; do
  gst sfx-normalize "$W/audio/sfx/${k}_0007.wav" -o "$P/audio/sfx/$k.wav" --peak -3
done

echo "== 8. Godot import presets =="
gst godot-import-presets "$P" -r data/import_rules.json --force

echo "== 9. previews =="
gst spritesheet-gif "$W/preview/player_sheet.json" -o "$W/preview/player_frames.gif" --scale 4 --bg "#5fa8e8"

if [ "$MODE" = "--verify" ] || [ "$MODE" = "--movie" ]; then
  : "${GODOT_BIN:?GODOT_BIN must point at Godot 4.7+}"
  godot_env
  echo "== 10. Godot headless import =="
  "$GODOT_BIN" --headless --path "$P" --import --quit > "$W/import.log" 2>&1 || true
  if grep -E "ERROR|SCRIPT ERROR|Failed" "$W/import.log"; then echo "import errors" >&2; exit 1; fi
  echo "import clean ($(wc -l < "$W/import.log") log lines)"
  echo "== 11. autoplay test =="
  timeout 300 "$GODOT_BIN" --headless --path "$P" --fixed-fps 60 -- --autoplay > "$W/autoplay.log" 2>&1 || true
  grep SAMPLE_GAME "$W/autoplay.log"
  if grep -E "SCRIPT ERROR|ERROR:|still in use" "$W/autoplay.log"; then echo "runtime errors" >&2; exit 1; fi
  grep -q "SAMPLE_GAME_LEVEL 3" "$W/autoplay.log" && grep -q "SAMPLE_GAME_DONE" "$W/autoplay.log"
fi
if [ "$MODE" = "--movie" ]; then
  echo "== 12. software-GL movie (26 s @ 30 fps) =="
  mkdir -p "$W/movie"
  LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe timeout 600 xvfb-run -a -s "-screen 0 1280x720x24" \
    "$GODOT_BIN" --path "$P" --display-driver x11 --rendering-driver opengl3 \
    --rendering-method gl_compatibility --resolution 640x360 --fixed-fps 30 --quit-after 780 \
    --write-movie "$W/movie/gameplay.avi" -- --autoplay > "$W/movie.log" 2>&1 || true
  ffmpeg -y -loglevel error -i "$W/movie/gameplay.avi" -vf "scale=640:360:flags=neighbor" -c:v libx264 -pix_fmt yuv420p -crf 20 -c:a aac -b:a 96k "$W/movie/gameplay.mp4"
  rm -rf "$W/movie/gif" && mkdir -p "$W/movie/gif"
  ffmpeg -y -loglevel error -i "$W/movie/gameplay.avi" -vf "fps=10,scale=320:-1:flags=neighbor" "$W/movie/gif/f_%04d.png"
  gst frames-to-sheet "$W/movie/gif" -o "$W/movie/gameplay_sheet" --columns 24 --no-crop
  gst spritesheet-gif "$W/movie/gameplay_sheet.json" -o "$W/movie/gameplay_raw.gif"
  gst gif-optimize "$W/movie/gameplay_raw.gif" -o "$W/movie/gameplay.gif" --colors 64
  rm -rf "$W/movie/gif" "$W/movie/gameplay_sheet.png" "$W/movie/gameplay_raw.gif"
  mkdir -p "$HERE/media"
  cp "$W/movie/gameplay.gif" "$W/movie/gameplay.mp4" "$HERE/media/"
  for shot in title:1.5 level2:12.5 level3:19.5 win:24.0; do
    ffmpeg -y -loglevel error -ss "${shot#*:}" -i "$W/movie/gameplay.avi" -frames:v 1 "$HERE/media/shot_${shot%%:*}.png"
  done
  grep SAMPLE_GAME "$W/movie.log" | tail -3
  ls -la "$HERE/media"
fi
echo "build.sh: done"
