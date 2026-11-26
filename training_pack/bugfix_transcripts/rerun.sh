#!/usr/bin/env bash
# Re-measure everything in runs/: needs a 2.4.0 worktree (git worktree add --detach /tmp/gst240 f750fe6) and GODOT_BIN.
set -u; H="$(cd "$(dirname "$0")" && pwd)"; KIT="$(cd "$H/../.." && pwd)"; OLD="${OLD:-/tmp/gst240}"
K="dungeon_gen or atlas_to_godot or anim_from_folder or asset_unused or nav_to_godot or bundle"
for b in "$H"/repro/bug*.sh; do n="$(basename "$b" .sh)"
  GST_ROOT="$OLD" bash "$b" > "$H/runs/${n}_240.txt" 2>&1; echo "exit=$?" >> "$H/runs/${n}_240.txt"
  GST_ROOT="$KIT" bash "$b" > "$H/runs/${n}_250.txt" 2>&1; echo "exit=$?" >> "$H/runs/${n}_250.txt"; done
(cd "$KIT" && python3 -m pytest -p no:cacheprovider -v tests/test_v25.py -k "$K" 2>&1 | tail -15) > "$H/runs/v250_tests.txt"
cp "$KIT/tests/test_v25.py" "$OLD/tests/" && (cd "$OLD" && python3 -m pytest -p no:cacheprovider -v tests/test_v25.py -k "$K" -rf) > "$H/runs/v240_tests_full.txt" 2>&1
python3 "$H/make_transcripts.py"
