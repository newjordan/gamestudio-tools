#!/usr/bin/env bash
# Rebuild every generated asset in this showcase from kit procedural tools.
# Authored files (project.godot, scenes, scripts, this script, bake_map.py, README)
# are left alone. Requires gst (on PATH or two directories above this script).
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
  echo "build_showcase.sh: gst not found (set GST_ROOT, install the kit, or run from a checkout)" >&2
  exit 2
fi

cd "$HERE"

wipe_generated() {
  rm -rf art sfx font preview frames .godot
  mkdir -p art/work sfx font preview
  printf '*\n' > preview/.gdignore
}

godot_env() {
  # Isolate Godot's user dir so a build never writes into the operator's real HOME.
  local home="${GST_GODOT_HOME:-}"
  if [ -z "$home" ]; then
    home="$(mktemp -d "${TMPDIR:-/tmp}/gst-showcase-godot.XXXXXX")"
    GST_GODOT_HOME="$home"
    export GST_GODOT_HOME
  fi
  mkdir -p "$home/.config" "$home/.local/share" "$home/.cache"
  export HOME="$home"
  export XDG_CONFIG_HOME="$home/.config"
  export XDG_DATA_HOME="$home/.local/share"
  export XDG_CACHE_HOME="$home/.cache"
}

run_godot() {
  local bin="${GODOT_BIN:-}"
  if [ -z "$bin" ] || [ ! -x "$bin" ]; then
    echo "GODOT_BIN is not set to an executable; skip Godot step: $*" >&2
    return 2
  fi
  godot_env
  "$bin" "$@"
}

wipe_generated

echo "== textures for tiles =="
gst tex-gen noise -o art/work/grass_src.png --size 64 --seed 1 --color-a "#3e8f3a" --color-b "#2d6b2a"
gst tex-gen noise -o art/work/dirt_src.png --size 64 --seed 2 --color-a "#8a6a3f" --color-b "#6b4e2e"

echo "== tileset (blob + wang + solid colliders) =="
gst tileset-gen -o art/tiles --tile 16 --border 4 \
  --inner art/work/grass_src.png --outer art/work/dirt_src.png --edge-color "#2a4a22"
# Slot 47 (empty on the 8x6 sheet) becomes a solid dirt wall tile; blob tile 0 is
# an isolated grass cap, not a full wall.
gst tex-gen noise -o art/work/wall16.png --size 16 --seed 2 --color-a "#8a6a3f" --color-b "#6b4e2e"
python3 "$HERE/stamp_tile.py" art/tiles.png art/work/wall16.png --index 47 --columns 8 --tile-size 16 -o art/tiles.png
gst tileset-wang art/tiles.json -o art/tiles_wang.json --kind blob \
  --image art/tiles.png --name ground --terrain grass --pretty
printf '%s\n' '{"solid":[47]}' > art/solid_ids.json
gst godot-tileset art/tiles.png -o art/tiles.tres \
  --tile 16 --columns 8 --res "res://art/tiles.png" \
  --colliders art/solid_ids.json --wang art/tiles_wang.json

echo "== dungeon map =="
gst dungeon-gen --mode bsp --size 20x14 --seed 42 --scale 8 -o art/dungeon
gst tile-colliders art/dungeon.json --solid 2 -o art/map_colliders.json
python3 "$HERE/bake_map.py" art/dungeon.json art/tiles.json --wall-id 47 -o art/cells.json

echo "== player walk frames =="
# Three slightly different procedural blobs, outlined, foot-anchored, with a
# contact shadow that shifts 1px so the clip reads as a waddle.
for seed in 11 12 13; do
  i=$((seed - 10))
  gst tex-gen cells -o "art/work/body_${i}.png" --size 32 --seed "$seed" --count 6 \
    --color-a "#3d7ea6" --color-b "#c8e4f0"
  gst pixelize "art/work/body_${i}.png" -o "art/work/pix_${i}.png" -w 10 --outline --colors 4 --nearest
  gst sprite-outline-gen "art/work/pix_${i}.png" -o "art/work/out_${i}.png" --width 1 --color "#1a1a2e" --keep-size
done
gst sprite-canvas art/work/out_1.png art/work/out_2.png art/work/out_3.png \
  -o art/work/canvas --size 16x16 --anchor feet
# sprite-canvas keeps source names; rename to walk_01..03 and offset shadows.
mkdir -p art/work/frames
i=1
for src in art/work/canvas/out_1.png art/work/canvas/out_2.png art/work/canvas/out_3.png; do
  dx=$((i - 2))
  gst sprite-shadow "$src" -o "art/work/frames/walk_0${i}.png" --mode contact --dx "$dx" --dy 1 --opacity 0.45 --keep-size
  i=$((i + 1))
done
mkdir -p art/work/frames
gst anim-from-folder art/work/frames -o art/walk_clips.json --pattern "{clip}_{frame}.png" --fps walk=8 --default-fps 8
gst atlas-pack art/work/frames -o art/player --padding 1 --no-pot --no-trim
gst atlas-to-godot art/player.json -o art/player_frames.tres \
  --clips art/walk_clips.json --sheet art/player.png --res "res://art/player.png"

echo "== step SFX + loudness =="
gst sfx-gen blip -o art/work --seed 7 -n 1
gst sfx-normalize art/work/blip_0007.wav -o art/work/step_norm.wav --peak -1.0
gst wav-loud-apply art/work/step_norm.wav --target -16 -o sfx --suffix _loud
mv -f sfx/step_norm_loud.wav sfx/step.wav

echo "== BMFont (Pillow default face, no vendored TTF) =="
gst bmfont-gen --font default --size 16 --no-aa --padding 1 \
  --chars "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789.-" \
  -o font/label

# Drop scratch textures so import presets only touch shipped PNGs.
rm -rf art/work

echo "== Godot import presets =="
gst godot-import-presets . -r import_rules.json

echo "== optional software-GL preview =="
preview_ok=0
if [ -n "${GODOT_BIN:-}" ] && [ -x "${GODOT_BIN}" ]; then
  echo "importing project with Godot..."
  mkdir -p preview/movie
  run_godot --headless --path "$HERE" --import --quit || true
  render_args=(
    --display-driver x11
    --rendering-driver opengl3
    --rendering-method gl_compatibility
    --disable-vsync
    --path "$HERE"
    --write-movie "$HERE/preview/movie/frame.png"
    --fixed-fps 10
    --quit-after 24
    --
    --preview
  )
  export LIBGL_ALWAYS_SOFTWARE=1
  export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
  if [ -n "${DISPLAY:-}" ]; then
    godot_env
    if timeout 90 "$GODOT_BIN" "${render_args[@]}"; then
      preview_ok=1
    else
      echo "Godot --write-movie on DISPLAY=$DISPLAY failed; trying xvfb-run" >&2
    fi
  fi
  if [ "$preview_ok" -eq 0 ] && command -v xvfb-run >/dev/null 2>&1; then
    godot_env
    if timeout 90 xvfb-run -a -s "-screen 0 640x480x24" env \
        HOME="$HOME" XDG_CONFIG_HOME="$XDG_CONFIG_HOME" \
        XDG_DATA_HOME="$XDG_DATA_HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" \
        LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}" \
        "$GODOT_BIN" "${render_args[@]}"; then
      preview_ok=1
    else
      echo "preview render failed (collision test does not need it)" >&2
    fi
  fi
  if [ "$preview_ok" -eq 1 ]; then
    rm -f preview/movie/frame.wav
    shopt -s nullglob
    movie_pngs=(preview/movie/frame*.png)
    shopt -u nullglob
    if [ "${#movie_pngs[@]}" -gt 0 ]; then
      gst frames-to-sheet preview/movie -o preview/sheet --no-crop --max-frames 24
      gst spritesheet-gif preview/sheet.json -o preview/showcase_raw.gif --fps 10 --scale 2 --bg "#1a1a2e"
      gst gif-optimize preview/showcase_raw.gif -o preview/showcase.gif --colors 48
      rm -f preview/showcase_raw.gif
      rm -rf preview/movie
      echo "wrote preview/showcase.gif from ${#movie_pngs[@]} movie frames"
    fi
  fi
else
  echo "GODOT_BIN unset; skipping import and preview render"
fi

echo "showcase assets rebuilt in $HERE"
