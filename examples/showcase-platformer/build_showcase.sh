#!/usr/bin/env bash
# Rebuild every generated asset in this side-view platformer showcase from kit
# procedural tools. Authored files (project.godot, scenes, scripts, this script,
# bake_level.py, README) are left alone. Requires gst (on PATH or two
# directories above this script).
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
  mkdir -p art/work/tiles art/work/frames sfx font preview
  printf '*\n' > preview/.gdignore
}

godot_env() {
  local home="${GST_GODOT_HOME:-}"
  if [ -z "$home" ]; then
    home="$(mktemp -d "${TMPDIR:-/tmp}/gst-showcase-platformer.XXXXXX")"
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

echo "== tiles (grass, dirt, one-way) =="
gst tex-gen noise -o art/work/tiles/t0_grass.png --size 16 --seed 31 --color-a "#4aaa3a" --color-b "#2e7a28"
gst tex-gen noise -o art/work/tiles/t1_dirt.png --size 16 --seed 32 --color-a "#8a6234" --color-b "#6a4522"
gst tex-gen planks -o art/work/tiles/t2_plat.png --size 16 --seed 33 --color-a "#c4a36a" --color-b "#8a6a38" --count 3
gst frames-to-sheet art/work/tiles -o art/tiles --columns 3 --no-crop --padding 0
printf '%s\n' '{
  "tiles": {
    "0": {"rects": [{"x": 0, "y": 0, "w": 16, "h": 16}]},
    "1": {"rects": [{"x": 0, "y": 0, "w": 16, "h": 16}]},
    "2": {"rects": [{"x": 0, "y": 0, "w": 16, "h": 8, "one_way": true}]}
  }
}' > art/colliders.json
gst godot-tileset art/tiles.png -o art/tiles.tres \
  --tile 16 --columns 3 --res "res://art/tiles.png" \
  --colliders art/colliders.json

echo "== blank map, bake tiles, validate gaps with jump-arc =="
gst map-blank -o art/blank.json --size 32x12 --tile 16 --layers ground,platforms \
  --tileset art/tiles.png --tilecount 3 --columns 3 --pretty
python3 "$HERE/bake_level.py" art/blank.json -o art/level.json --cells art/cells.json

# Physics in cells.json must match project.godot and the Godot script.
python3 - "$HERE" << 'PY'
import json, pathlib, sys
here = pathlib.Path(sys.argv[1])
cells = json.loads((here / "art/cells.json").read_text())
assert cells["gravity"] == 800 and cells["jump_v"] == 220 and cells["speed"] == 120
(here / "art/gaps.json").write_text(json.dumps(cells["gaps"], indent=2))
print("physics", cells["gravity"], cells["jump_v"], cells["speed"], "gaps", len(cells["gaps"]))
PY

# iterate gaps from cells.json
python3 - "$HERE" << 'PY'
import json, os, pathlib, shutil, subprocess, sys
here = pathlib.Path(sys.argv[1])
cells = json.loads((here / "art/cells.json").read_text())
root = pathlib.Path(os.environ["GST_ROOT"]) if os.environ.get("GST_ROOT") else here.parents[1]
gst = root / "gst"
if not gst.is_file():
    found = shutil.which("gst")
    if not found:
        raise SystemExit("gst not found: set GST_ROOT")
    gst = pathlib.Path(found)
for i, g in enumerate(cells["gaps"], start=1):
    sx, sy = g["takeoff"]
    jpath = here / "art" / f"jump_gap{i}.json"
    ppath = here / "art" / f"jump_gap{i}.png"
    cmd = [
        sys.executable, str(gst), "jump-arc", str(here / "art/level.json"),
        "-o", str(ppath),
        "--start", f"{sx},{sy}",
        "--jump-v", str(cells["jump_v"]),
        "--speed", str(cells["speed"]),
        "--gravity", str(cells["gravity"]),
        "--solid-layer", "ground",
        "--json", str(jpath),
    ]
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    subprocess.check_call([
        sys.executable, str(here / "bake_level.py"),
        "--check-arc", str(jpath),
        "--land-min", str(g["land_min"]),
        "--land-max", str(g["land_max"]),
        "--floor-y", str(g["floor_y"]),
    ])
PY

echo "== player walk frames =="
for seed in 41 42 43; do
  i=$((seed - 40))
  gst tex-gen cells -o "art/work/body_${i}.png" --size 32 --seed "$seed" --count 6 \
    --color-a "#c45c2a" --color-b "#f0d2a8"
  gst pixelize "art/work/body_${i}.png" -o "art/work/pix_${i}.png" -w 10 --outline --colors 4 --nearest
  gst sprite-outline-gen "art/work/pix_${i}.png" -o "art/work/out_${i}.png" --width 1 --color "#1a1a2e" --keep-size
done
gst sprite-canvas art/work/out_1.png art/work/out_2.png art/work/out_3.png \
  -o art/work/canvas --size 16x16 --anchor feet
i=1
for src in art/work/canvas/out_1.png art/work/canvas/out_2.png art/work/canvas/out_3.png; do
  dx=$((i - 2))
  gst sprite-shadow "$src" -o "art/work/frames/walk_0${i}.png" --mode contact --dx "$dx" --dy 1 --opacity 0.45 --keep-size
  i=$((i + 1))
done
gst anim-from-folder art/work/frames -o art/walk_clips.json --pattern "{clip}_{frame}.png" --fps walk=8 --default-fps 8
gst atlas-pack art/work/frames -o art/player --padding 1 --no-pot --no-trim
gst atlas-to-godot art/player.json -o art/player_frames.tres \
  --clips art/walk_clips.json --sheet art/player.png --res "res://art/player.png"

echo "== coin sprite + pickup SFX =="
gst tex-gen cells -o art/work/coin_src.png --size 32 --seed 9 --count 5 \
  --color-a "#e8c030" --color-b "#fff4a0"
gst pixelize art/work/coin_src.png -o art/work/coin_pix.png -w 10 --outline --colors 4 --nearest
gst sprite-outline-gen art/work/coin_pix.png -o art/work/coin_out.png --width 1 --color "#5a3a00" --keep-size
gst sprite-canvas art/work/coin_out.png -o art/work/coin_canvas --size 16x16 --anchor center
cp art/work/coin_canvas/coin_out.png art/coin.png
gst sfx-gen coin -o art/work --seed 3 -n 1
gst sfx-normalize art/work/coin_0003.wav -o sfx/coin.wav --peak -1.0

echo "== parallax layers (tex-gen + sprite-canvas crop, then parallax-preview) =="
gst tex-gen noise -o art/work/sky_src.png --size 640 --seed 21 --color-a "#8fd4ff" --color-b "#3a7ebe"
gst sprite-canvas art/work/sky_src.png -o art/work/sky_canvas --size 640x180 --anchor center
cp art/work/sky_canvas/sky_src.png art/parallax_far.png
# Crop a short band of mid / near texture, then pad onto a 640x180 canvas so
# the upper sky stays visible and only a silhouette sits near the horizon.
gst tex-gen noise -o art/work/mid_src.png --size 640 --seed 22 --color-a "#3d7a45" --color-b "#1e4a28"
gst sprite-canvas art/work/mid_src.png -o art/work/mid_band --size 640x64 --anchor s
gst sprite-canvas art/work/mid_band/mid_src.png -o art/work/mid_canvas --size 640x180 --anchor s
cp art/work/mid_canvas/mid_src.png art/parallax_mid.png
gst tex-gen noise -o art/work/near_src.png --size 640 --seed 23 \
  --color-a "#16301a" --color-b "#0a180c"
gst sprite-canvas art/work/near_src.png -o art/work/near_band --size 640x40 --anchor s
gst sprite-canvas art/work/near_band/near_src.png -o art/work/near_canvas --size 640x180 --anchor s
cp art/work/near_canvas/near_src.png art/parallax_near.png
gst parallax-preview art/parallax_far.png art/parallax_mid.png art/parallax_near.png \
  -o preview/parallax.gif --speeds 0.15,0.4,0.8 --width 320 --height 180 --frames 24 --fps 10 \
  --png preview/parallax_frame.png --bg "#6eb4e6"

echo "== BMFont HUD =="
gst bmfont-gen --font default --size 16 --no-aa --padding 1 \
  --chars "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789.-" \
  -o font/label

rm -rf art/work art/blank.json

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
    --quit-after 36
    --
    --preview
  )
  export LIBGL_ALWAYS_SOFTWARE=1
  export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
  if [ -n "${DISPLAY:-}" ]; then
    godot_env
    if timeout 120 "$GODOT_BIN" "${render_args[@]}"; then
      preview_ok=1
    else
      echo "Godot --write-movie on DISPLAY=$DISPLAY failed; trying xvfb-run" >&2
    fi
  fi
  if [ "$preview_ok" -eq 0 ] && command -v xvfb-run >/dev/null 2>&1; then
    godot_env
    if timeout 120 xvfb-run -a -s "-screen 0 640x480x24" env \
        HOME="$HOME" XDG_CONFIG_HOME="$XDG_CONFIG_HOME" \
        XDG_DATA_HOME="$XDG_DATA_HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" \
        LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}" \
        "$GODOT_BIN" "${render_args[@]}"; then
      preview_ok=1
    else
      echo "preview render failed (jump landing test does not need it)" >&2
    fi
  fi
  if [ "$preview_ok" -eq 1 ]; then
    rm -f preview/movie/frame.wav
    shopt -s nullglob
    movie_pngs=(preview/movie/frame*.png)
    shopt -u nullglob
    if [ "${#movie_pngs[@]}" -gt 0 ]; then
      gst frames-to-sheet preview/movie -o preview/sheet --no-crop --max-frames 36
      gst spritesheet-gif preview/sheet.json -o preview/showcase_raw.gif --fps 10 --scale 2 --bg "#6eb4e6"
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
