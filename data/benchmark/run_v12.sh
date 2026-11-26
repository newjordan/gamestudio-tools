#!/bin/bash
# Benchmark v1.2: default scale, seeds 0,1,2, tasks that use class labels (T2, T2-occ) plus T3 (no labels, protocol check) and the T1-norm resolution-leak probe.
# Resumable. Does not touch v1 or v1.1 runs.
cd "$(dirname "$0")"
MAP="$PWD/class_map_v1.2.json"
note() { echo "- $(date '+%Y-%m-%d %H:%M:%S %Z') $*" >> PROGRESS.md; }
TASKS=(T2_sprite_sem T2_sprite_sem_occ T3_game_retrieval T6_resleak T6_resleak_stretch)
for s in 0 1 2; do
  if python3 - <<PY
import json,sys
try: sys.exit(0 if "finished" in json.load(open("runs/v12_default_seed$s/results.json")) else 1)
except Exception: sys.exit(1)
PY
  then note "seed $s already finished, skipped"; continue; fi
  note "seed $s start (disk: $(df -h /workspace | awk 'NR==2{print $4}') free)"
  python3 -m gbench --class-map "$MAP" run --scale default --seed $s --name v12_default_seed$s --resume --tasks "${TASKS[@]}" >> runs/run_v12.out 2>&1 || { note "seed $s FAILED rc=$?"; exit 1; }
  note "seed $s done"
done
python3 -m gbench report >> runs/run_v12.out 2>&1 && note "report written (RESULTS.md, BENCHMARK.md block)"
note "ALL DONE"
