#!/usr/bin/env bash
# Rebuild every generated asset in this HTML5 canvas showcase from kit
# procedural tools. Authored files (index.html, js/, bake_room.py, this
# script, README) are left alone. Requires gst (on PATH or two directories
# above this script). No Godot.
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
  rm -rf art sfx font preview frames
  mkdir -p art/work/tiles art/work/frames sfx font preview/frames
}

crop_canvas() {
  # Usage: crop_canvas IN OUT  — keep the 640x360 canvas at top-left if padded.
  python3 - "$1" "$2" << 'PY'
import sys
from PIL import Image
src, dest = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
w, h = im.size
cw, ch = 640, 360
if w >= cw and h >= ch:
    im = im.crop((0, 0, cw, ch))
im.save(dest)
print("cropped", dest, im.size)
PY
}

capture_previews() {
  if ! command -v cutycapt >/dev/null 2>&1; then
    echo "cutycapt not found; skip live preview capture" >&2
    return 0
  fi
  local portfile log server_pid port i=0
  portfile="$(mktemp "${TMPDIR:-/tmp}/gst-web-port.XXXXXX")"
  log="$(mktemp "${TMPDIR:-/tmp}/gst-web-http.XXXXXX")"
  python3 - "$HERE" "$portfile" << 'PY' &
import http.server, os, pathlib, sys
root = pathlib.Path(sys.argv[1])
portfile = pathlib.Path(sys.argv[2])
os.chdir(root)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
portfile.write_text(str(httpd.server_address[1]), encoding="utf-8")
try:
    httpd.serve_forever()
finally:
    httpd.server_close()
PY
  server_pid=$!
  trap 'kill "$server_pid" 2>/dev/null || true; rm -f "$portfile"' RETURN

  port=""
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if [ -s "$portfile" ]; then
      port="$(cat "$portfile")"
      break
    fi
    sleep 0.1
  done
  if [ -z "$port" ]; then
    echo "http server did not publish a port; skip preview capture" >&2
    cat "$log" >&2 || true
    return 0
  fi

  run_cuty() {
    local url="$1" dest="$2"
    local args=(--url="$url" --out="$dest" --delay=1500 --min-width=640 --min-height=360 --javascript=on --auto-load-images=on --max-wait=20000)
    if [ -n "${DISPLAY:-}" ]; then
      if timeout 30 cutycapt "${args[@]}"; then
        return 0
      fi
      echo "cutycapt on DISPLAY=$DISPLAY failed; trying xvfb-run" >&2
    fi
    if command -v xvfb-run >/dev/null 2>&1; then
      timeout 30 xvfb-run -a -s "-screen 0 800x600x24" cutycapt "${args[@]}"
    else
      echo "no xvfb-run and no usable DISPLAY; cannot capture $url" >&2
      return 1
    fi
  }

  local steps=(0 6 12 18 24 30 36 42 48 54 60 66)
  local step url raw dest n=0
  mkdir -p preview/frames
  for step in "${steps[@]}"; do
    raw="preview/frames/_raw_${step}.png"
    dest="$(printf 'preview/frames/frame_%02d.png' "$n")"
    url="http://127.0.0.1:${port}/index.html?preview=1&muted=1&step=${step}"
    if ! run_cuty "$url" "$raw"; then
      echo "capture failed at step=$step" >&2
      return 0
    fi
    crop_canvas "$raw" "$dest"
    rm -f "$raw"
    n=$((n + 1))
  done

  cp -f preview/frames/frame_00.png preview/shot_00.png
  cp -f preview/frames/frame_04.png preview/shot_08.png   # step 24 ≈ 0.8s
  cp -f preview/frames/frame_08.png preview/shot_16.png   # step 48 ≈ 1.6s
  cp -f preview/shot_00.png preview/showcase.png

  gst frames-to-sheet preview/frames -o preview/sheet --no-crop --max-frames 12
  gst spritesheet-gif preview/sheet.json -o preview/showcase_raw.gif --fps 10 --bg "#0e1116"
  gst gif-optimize preview/showcase_raw.gif -o preview/showcase.gif --colors 48
  rm -f preview/showcase_raw.gif
  echo "wrote preview/showcase.gif and shot PNGs"
}

wipe_generated

echo "== tiles (floor, wall) =="
gst tex-gen noise -o art/work/tiles/t0_floor.png --size 16 --seed 41 --color-a "#3d5a4c" --color-b "#2a3f36"
gst tex-gen cells -o art/work/tiles/t1_wall.png --size 16 --seed 42 --count 4 --color-a "#4a3b2f" --color-b "#2a221c"
gst frames-to-sheet art/work/tiles -o art/tiles --columns 2 --no-crop --padding 0

echo "== blank map, bake room, confirm a path to the coin =="
gst map-blank -o art/blank.json --size 20x10 --tile 16 --layers ground,walls \
  --tileset art/tiles.png --tilecount 2 --columns 2 --pretty
python3 "$HERE/bake_room.py" art/blank.json -o art/level.json --tileset art/tiles.png
gst map-path art/level.json --start-name spawn --goal-name coin --solid-layer walls \
  --json art/path.json --png preview/path.png --fail-if-none

echo "== player walk frames + coin =="
for seed in 21 22 23; do
  i=$((seed - 20))
  gst tex-gen cells -o "art/work/body_${i}.png" --size 32 --seed "$seed" --count 6 \
    --color-a "#6a3d9a" --color-b "#e8d4f8"
  gst pixelize "art/work/body_${i}.png" -o "art/work/pix_${i}.png" -w 10 --outline --colors 4 --nearest
  gst sprite-outline-gen "art/work/pix_${i}.png" -o "art/work/out_${i}.png" --width 1 --color "#1a1a2e" --keep-size
done
gst sprite-canvas art/work/out_1.png art/work/out_2.png art/work/out_3.png \
  -o art/work/canvas --size 16x16 --anchor feet
gst sprite-reframe art/work/canvas -o art/work/reframed --size 16x16 --anchor feet
mkdir -p art/work/frames
i=1
for src in art/work/reframed/out_1.png art/work/reframed/out_2.png art/work/reframed/out_3.png; do
  dx=$((i - 2))
  gst sprite-shadow "$src" -o "art/work/frames/walk_0${i}.png" --mode contact --dx "$dx" --dy 1 --opacity 0.45 --keep-size
  i=$((i + 1))
done
gst tex-gen cells -o art/work/coin_src.png --size 32 --seed 9 --count 5 --color-a "#e0b000" --color-b "#fff3a0"
gst pixelize art/work/coin_src.png -o art/work/coin_pix.png -w 8 --outline --colors 4 --nearest
gst sprite-outline-gen art/work/coin_pix.png -o art/work/coin_out.png --width 1 --color "#1a1a2e" --keep-size
gst sprite-canvas art/work/coin_out.png -o art/work/coin_canvas --size 16x16 --anchor center
cp -f art/work/coin_canvas/coin_out.png art/work/frames/coin.png
gst atlas-pack art/work/frames -o art/player --padding 1 --no-pot --no-trim
gst atlas-sort art/player.json -o art/player_sorted.json --by name
mv -f art/player_sorted.json art/player.json

echo "== coin SFX + loudness =="
gst sfx-gen coin -o art/work --seed 5 -n 1
gst sfx-normalize art/work/coin_0005.wav -o art/work/coin_norm.wav --peak -1.0
gst wav-gate art/work/coin_norm.wav -o sfx/coin.wav --thresh-db -40 --attack-ms 2 --hold-ms 10 --release-ms 20

echo "== BMFont (Pillow default face, no vendored TTF) =="
gst bmfont-gen --font default --size 16 --no-aa --padding 1 \
  --chars "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789.-" \
  -o font/label

rm -rf art/work

echo "== optional live preview (CutyCapt + Xvfb) =="
capture_previews || echo "preview capture failed (parse test does not need it)" >&2

echo "showcase assets rebuilt in $HERE"
