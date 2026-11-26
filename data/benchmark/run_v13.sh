#!/bin/bash
# Benchmark v1.3: anti-leak T1 protocols. Default scale, seeds 0,1,2.
# One python invocation per protocol × seed (T1_norm + T6 letterbox + T6 stretch).
# Does not touch v1, v1.1, or v1.2 runs or manifests.
set -euo pipefail
cd "$(dirname "$0")"
MAP="$PWD/class_map_v1.2.json"
note() { echo "- $(date '+%Y-%m-%d %H:%M:%S %Z') $*" | tee -a PROGRESS.md; }
free() { df -h /workspace | awk 'NR==2{print $4}'; }
PROTOS=(bn64 bn96 bn64_blur bn64_jpeg)
TASKS=(T1_norm T6_resleak T6_resleak_stretch)

mkdir -p runs
: >> runs/run_v13.out
note "v1.3 runner start, disk $(free) free"
for proto in "${PROTOS[@]}"; do
  for s in 0 1 2; do
    out="runs/v13_${proto}_default_seed${s}"
    if python3 - <<PY
import json,sys
try:
    R=json.load(open("$out/results.json"))
except Exception:
    sys.exit(1)
need=["T1_norm","T6_resleak","T6_resleak_stretch"]
sys.exit(0 if "finished" in R and all(t in R.get("tasks",{}) for t in need) else 1)
PY
    then
      note "$proto seed $s already finished, skipped"
      continue
    fi
    note "$proto seed $s start (disk: $(free) free)"
    python3 -m gbench --class-map "$MAP" run --scale default --seed "$s" \
      --norm-protocol "$proto" --name "v13_${proto}_default_seed${s}" --resume \
      --tasks "${TASKS[@]}" >> runs/run_v13.out 2>&1 || { note "$proto seed $s FAILED rc=$?"; exit 1; }
    note "$proto seed $s done (disk: $(free) free)"
  done
done
note "all v1.3 seeds finished; writing report"
python3 -m gbench report >> runs/run_v13.out 2>&1 && note "report written (RESULTS.md, BENCHMARK.md block)"
note "ALL DONE v1.3"
