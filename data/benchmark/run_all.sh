#!/bin/bash
# v1 script, frozen: v1 results (runs/default_seed*, runs/large_seed0) were produced by gbench 0.1.0 and must not be overwritten.
# Use ./run_v11.sh for the v1.1 set. For a v1.1-code large run: python3 -m gbench run --scale large --seed 0 --name v11_large_seed0
echo "run_all.sh is the frozen v1 recipe; refusing to overwrite v1 results. Use run_v11.sh." >&2
exit 1
