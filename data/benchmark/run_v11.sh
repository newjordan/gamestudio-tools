#!/bin/bash
# Benchmark v1.1: default scale, seeds 0,1,2, all tasks. Resumable: finished runs are skipped,
# an unfinished run keeps its finished tasks (--resume) and reuses feature caches.
cd "$(dirname "$0")"
note() { echo "- $(date '+%Y-%m-%d %H:%M:%S %Z') $*" >> PROGRESS.md; }
python3 -m gbench classmap >> runs/run_v11.out 2>&1
for s in 0 1 2; do
  if python3 - <<PY
import json,sys
try: sys.exit(0 if "finished" in json.load(open("runs/v11_default_seed$s/results.json")) else 1)
except Exception: sys.exit(1)
PY
  then note "seed $s already finished, skipped"; continue; fi
  note "seed $s start"
  python3 -m gbench run --scale default --seed $s --name v11_default_seed$s --resume >> runs/run_v11.out 2>&1 || { note "seed $s FAILED rc=$?"; exit 1; }
  note "seed $s done"
done
python3 -m gbench report >> runs/run_v11.out 2>&1 && note "report written (RESULTS.md, BENCHMARK.md block)"
note "ALL DONE"
