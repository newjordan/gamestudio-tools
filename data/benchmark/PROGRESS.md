# PROGRESS — benchmark v1.2 (started 2026-11-25 12:56 CST)
Resume rule: v1 (runs/default_seed*, runs/large_seed0, runs_v1_manifest.sha256, RESULTS_v1.md, BENCHMARK_v1.md) and v1.1 (runs/v11_default_seed*, runs_v11_manifest.sha256, RESULTS_v11.md, BENCHMARK_v11.md, CLASSMAP_AUDIT_v11.md) are frozen. Never overwrite them. v1.2 runs go to runs/v12_*. `run_v12.sh` skips finished runs and resumes unfinished ones.
- [x] 0. snapshot v1.1 (RESULTS, BENCHMARK, CLASSMAP_AUDIT, manifests, sha256)
- [x] 1. disk 6.1G free at start; v1+v1.1 snapshots intact. disk check; free rebuildable caches if needed (never results or clean_v1)
- [x] 2. class map v1.2 written (20 classes, 186,118 boxes; tree hand-labels left alone). class map v1.2: evidence from source metadata, document every change + box counts
- [x] 3. tests: 53 pass including 8 new v1.2 tests. tests for the new map + leak probe (all existing tests still pass)
- [x] 4-5. default seeds 0,1,2 finished (13:05-13:13 CST); T3 135/135 identical to v1.1.
- [ ] 5. rerun T2 / T2-occ (class labels) default seeds 0,1,2 with the v1.2 map; T3 does not use class labels
- [x] 6. RESULTS.md + BENCHMARK.md updated from runs.

## Run log
- 2026-11-25 12:55:58 CST v1.1 snapshot written; v1 manifest still OK
- 2026-11-25 13:04:56 CST launching run_v12.sh
- 2026-11-25 13:05:31 CST seed 0 start (disk: 6.1G free)
- 2026-11-25 13:08:04 CST seed 0 done
- 2026-11-25 13:08:04 CST seed 1 start (disk: 6.0G free)
- 2026-11-25 13:10:45 CST seed 1 done
- 2026-11-25 13:10:45 CST seed 2 start (disk: 5.7G free)
- 2026-11-25 13:13:21 CST seed 2 done
- 2026-11-25 13:13:21 CST report written (RESULTS.md, BENCHMARK.md block)
- 2026-11-25 13:13:21 CST ALL DONE
- 2026-11-25 13:16:16 CST v1.2 report finalised; v1 and v1.1 manifests still OK

# v1.3
- 2026-11-25 13:21:18 CST froze v1.2: RESULTS_v12.md, BENCHMARK_v12.md, runs_v12_manifest.sha256 (verified)
- 2026-11-25 13:25:36 CST deleted rebuildable crop caches (52 files) to free disk; starting run_v13.sh
- 2026-11-25 13:25:59 CST v1.3 runner start, disk 6.4G free
- 2026-11-25 13:25:59 CST bn64 seed 0 start (disk: 6.4G free)
- 2026-11-25 13:30:03 CST bn64 seed 0 done (disk: 6.3G free)
- 2026-11-25 13:30:03 CST bn64 seed 1 start (disk: 6.3G free)
- 2026-11-25 13:33:37 CST bn64 seed 1 done (disk: 6.2G free)
- 2026-11-25 13:33:37 CST bn64 seed 2 start (disk: 6.2G free)
- 2026-11-25 13:36:16 CST bn64 seed 2 done (disk: 6.1G free)
- 2026-11-25 13:36:16 CST bn96 seed 0 start (disk: 6.1G free)
- 2026-11-25 13:38:59 CST bn96 seed 0 done (disk: 6.0G free)
- 2026-11-25 13:38:59 CST bn96 seed 1 start (disk: 6.0G free)
- 2026-11-25 13:41:21 CST bn96 seed 1 done (disk: 5.8G free)
- 2026-11-25 13:41:21 CST bn96 seed 2 start (disk: 5.8G free)
- 2026-11-25 13:43:54 CST bn96 seed 2 done (disk: 5.7G free)
- 2026-11-25 13:43:55 CST bn64_blur seed 0 start (disk: 5.7G free)
- 2026-11-25 13:46:39 CST bn64_blur seed 0 done (disk: 5.6G free)
- 2026-11-25 13:46:39 CST bn64_blur seed 1 start (disk: 5.6G free)
- 2026-11-25 13:49:22 CST bn64_blur seed 1 done (disk: 5.5G free)
- 2026-11-25 13:49:22 CST bn64_blur seed 2 start (disk: 5.5G free)
- 2026-11-25 13:52:31 CST bn64_blur seed 2 done (disk: 5.4G free)
- 2026-11-25 13:52:31 CST bn64_jpeg seed 0 start (disk: 5.4G free)
- 2026-11-25 13:55:58 CST bn64_jpeg seed 0 done (disk: 5.2G free)
- 2026-11-25 13:55:58 CST bn64_jpeg seed 1 start (disk: 5.2G free)
- 2026-11-25 13:59:11 CST bn64_jpeg seed 1 done (disk: 5.1G free)
- 2026-11-25 13:59:11 CST bn64_jpeg seed 2 start (disk: 5.1G free)
- 2026-11-25 14:02:43 CST bn64_jpeg seed 2 done (disk: 5.0G free)
- 2026-11-25 14:02:43 CST all v1.3 seeds finished; writing report
- 2026-11-25 14:02:44 CST report written (RESULTS.md, BENCHMARK.md block)
- 2026-11-25 14:02:44 CST ALL DONE v1.3
- 2026-11-25 14:06:55 CST official T1 = bn64; RESULTS/BENCHMARK/CARD written; v13 manifest verified; tests rerun
- 2026-11-25 14:08:22 CST resumed after interrupt: verified tree (63 tests pass, 4 manifests OK), fixed v1.3 seeds heading, refreshed RESULTS_v13/BENCHMARK_v13 + manifest. v1.3 COMPLETE
