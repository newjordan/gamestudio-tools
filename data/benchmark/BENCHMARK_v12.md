# gbench — CPU evaluation benchmark for the clean_v1 game-frame dataset

Owner: Jordan Newman, OmniSpace Technologies LLC. Benchmark v1.2 (gbench 0.3.0), 2026-11-25. v1 and v1.1 are kept for comparison: v1 is `BENCHMARK_v1.md`, `RESULTS_v1.md`, `runs/default_seed{0,1,2}`, `runs/large_seed0` (sha256 in `runs_v1_manifest.sha256`); nothing in them was touched.

## What changed in v1.1
1. **T1-norm** (`T1_norm`, `T1_norm_stretch`): every frame is resized to 256×256 before any feature is computed (letterboxed with black bars, or stretched with no bars). The size-only control sees the size the model sees (constant) and is checked against chance in every run (`shortcut_check` in results.json). The native frame size is kept as a separate, clearly labelled metadata control (`native_size_*`).
2. **T2 occlusion filter** (`T2_sprite_sem_occ`, option `--occ-min-visible`, `--occ-min-in-frame`): reported next to unfiltered T2 in every run, with a per-source table of what it removed. The class-map quirks are documented below and in `CLASSMAP_AUDIT.md`.
3. **T4 tiers**: mild (unchanged, pooled `mild_all` = v1's `all`) and hard (six stronger perturbations, pooled `hard_all`).
4. v1 tasks T1, T2, T3, T5 and the mild T4 are unchanged; the report prints a protocol check that counts the cells identical between v1 and v1.1 runs.
Scope: evaluation only. No model is trained on the dataset here (training stays on hold and, when it happens, runs on the DGX Sparks with Jordan's yes). The "learned" baseline is a small numpy logistic regression on hand-made features, fitted on the train sample inside each run. No pretrained weights, no Hugging Face, no GPU.


## What changed in v1.2
1. **Class map v1.2** (`class_map_v1.2.json`), built from a snapshot of `ALL/class_map.json` (that file was not modified; sha256 still matches `class_map_v1.json`). 20 classes / 186,118 boxes remapped, all with source-metadata evidence, listed in `CLASSMAP_AUDIT.md`: all synth `card_hearts*` item→card (91,106 boxes); 12 synth `character_*` classes prop→character (81,122); `tree_large` and `tree_small` prop→decor (13,890). synth `tree` (25,773) and `dead_tree` (4,050) stay prop because the generator's hand-read tile maps assign them to prop. No new vocabulary (no "agent" class).
2. **Game-scoped lookup.** v1.1 looked up only the bare raw class, so already-documented `game/raw` keys (from `class_overrides.tsv` and `GAME_RULES`) were ignored. v1.2 prefers `game/raw`, then the bare class. This is a lookup fix, not a new mapping. It is the main reason T2 crop counts rose.
3. **T6 resolution-leak probe.** From T1-norm features only, predict a native max-side bucket (`<=256`, `257-512`, `>512`). Size-only controls must stay at chance (three-class balanced accuracy 1/3). The stretch variant has no letterbox bars, so it is the cleaner test of upscaling traces.
4. T2 and T2-occ were rerun on default seeds 0,1,2 with the v1.2 map. T3 (no class labels) was rerun as a protocol check. v1 and v1.1 result files were not touched.


## Data it reads (read-only)
- Splits: `/workspace/gamedata-work/clean_v1/splits_v1/{train,val,test_seen,test_unseen}.jsonl` (sha256 of each file is stored in every run's `results.json`). `reserve`, `licence_review` and `removed` are never read, so frames whose art licence is unverified stay out of the benchmark.
- Licence manifest: `clean_v1/licence_manifest.csv`; `gbench check` fails if any evaluated game is missing from it.
- Label records: the `rec`/`off` pointer of each row (plain `records.jsonl` seek, or the sealed `records.jsonl.gz` member-offset scheme), images under `/workspace/gamedata/<path>`, shared classes from `/workspace/gamedata/ALL/class_map.json`.
- Nothing in `clean_v1` is written. Feature caches go to `benchmark/features/` (rebuildable; safe to delete).

## Evaluation splits
| name | what it is |
|---|---|
| seen (`test_seen`) | held-back runs of games that are in train |
| unseen (`test_unseen`) | the released split: whole held-out games for 19 sources; for **synth and roguelike** it holds out *kinds* (genre, render/tileset, seed) of games whose name is also in train — by design, see `gamedata/DATASET.md` |
| unseen-games (`test_unseen_games`) | strict subset of `test_unseen` whose (source, game) never appears in train/val/test_seen. Use this for "new game" claims. |

Leak checks run before every run and abort it on failure: no run or md5 shared between train and any eval split; no held-out game of a whole-game source present in train/val/test_seen.

## Tasks and metrics
| id | input → target | protocol | metrics |
|---|---|---|---|
| T1_source_id | full frame → engine/source (20 sources with train frames; cocos2d has none) | fit on train sample, pick L2 on val macro-F1, score seen / unseen / unseen-games | accuracy, **macro-F1**, balanced accuracy |
| T1_norm | as T1, every frame letterboxed to 256×256 first | as T1; size controls: `size_*` (model-visible size, must be near chance) and `native_size_*` (original size, metadata control) | accuracy, macro-F1, balanced accuracy |
| T1_norm_stretch | as T1, every frame stretched to 256×256 first (no bars) | as T1_norm | same |
| T2_sprite_sem | entity crop cut from the exact engine box → shared `sem` class (14; `unknown` dropped) | as T1; crops ≥ 8×8 px after clipping to the frame, ≤ 3 per frame | accuracy, **macro-F1**, balanced accuracy |
| T2_sprite_sem_occ | as T2 after the occlusion filter (train and eval) | drops entities that are vanished, truncated, visible < 0.5 (`visible_frac`, else `visibility`), occluded (godot fraction > 0.5, luanti flag) or < 80 % inside the frame; applied before the per-frame crop cap, so crop counts stay similar while the content changes | accuracy, macro-F1 |
| T3_game_retrieval | frame → other frames of the same game | seen: test_seen queries vs train gallery; unseen / unseen-games: leave-one-out inside the split with the query's own run removed from the gallery | R@1, R@5, R@10, **mAP** (queries without a positive are skipped and counted in `n_queries`) |
| T4_near_dup | perturbed frame → its exact original | gallery = every test_unseen sample frame; queries = a seeded subset, each under every perturbation. **Mild tier:** 0.5× rescale, JPEG q40, brightness ×1.25+10, 5 % border crop. **Hard tier:** 0.25× rescale, JPEG q10, colour cast (channel gains 1.3/0.8/1.1, +25), 15 % crop per side, Gaussian blur r=1.5 + noise σ=12, and a combination (10 % crop, 0.5×, JPEG q25, ×1.2+15) | **R@1**, mAP, per perturbation and pooled |
| T5_style_cluster | unsupervised palette/style grouping | k-means (k-means++, 3 inits) with k = number of games, on unseen-games and on unseen | NMI, **ARI**, purity vs game; NMI vs source |

T1 vs unseen-games is the generalisation question: does the source signature carry to games never seen? The seen − unseen gap in RESULTS.md quantifies it per method.

## Baselines (all CPU, computed on this box)
| name | tasks | what |
|---|---|---|
| random | all | seeded uniform labels / random ranking / random cluster ids |
| majority | T1, T2 | most frequent train class |
| hist_knn_k1, hist_knn_k10 | T1, T2 | 8×8×8 RGB histogram, Hellinger (sqrt-hist dot) kNN; k=10 is majority vote, ties to nearest |
| phash_knn_k1 | T1, T2 | 64-bit DCT perceptual hash, Hamming 1-NN |
| logreg_size_only, size_knn_k10 | T1, T1-norm, T2 | shortcut probes: logistic regression / 10-NN on log width, log height, log aspect only (frame size for T1, box size for T2). On T1-norm they see 256×256 for every frame, so they collapse to the class prior (seeded random tie-breaking) |
| native_size_logreg, native_size_knn_k10 | T1-norm | the same probes fed the ORIGINAL frame size: not an input of any normalised baseline; shows how much of T1 the hidden metadata shortcut would still carry |
| logreg_hist+simple | T1, T2 | numpy softmax regression (Adam, 300 full-batch epochs, inverse-frequency class weights, L2 picked on val from 1e-4/1e-3/1e-2) on sqrt-hist + 132 simple features (4×4 RGB and 8×8 grey thumbnails, gradient stats, RGB/HSV moments, aspect, distinct-colour count) |
| hist_hellinger, phash_hamming, dhash_hamming, simple_cosine | T3, T4 | ranking by histogram similarity, pHash / dHash Hamming distance, cosine on standardised simple features |
| kmeans_hist, kmeans_simple | T5 | k-means on sqrt-hist or standardised simple features |

scikit-learn and scipy are not installed on the box, so every metric and model is plain numpy (checked against hand-computed values in the tests).

## Reproduce
```bash
cd /workspace/gamedata-work/benchmark
python3 -m gbench check                       # leak + licence checks only
python3 -m gbench run --scale default --seed 0  # v1.1: ~5-6 min on 8 CPUs; writes runs/v11_default_seed0/{run.log,results.json}; --resume continues an interrupted run
./run_v11.sh                                  # the v1.1 set: default seeds 0,1,2, resumable, logs to PROGRESS.md, then report
./run_all.sh                                  # frozen v1 recipe; now refuses to run so v1 results cannot be overwritten
python3 -m gbench classmap                    # CLASSMAP_AUDIT.md from ALL/class_map.json
python3 -m gbench report                      # RESULTS.md + the block below, generated from results.json files
python3 -m pytest -q tests                    # harness tests on a generated toy dataset
```
Scales (per-game frame caps, so synth's 50 % share and big games do not swamp the sample): `smoke` 4/2/3/3, `default` 40/15/30/30, `large` 120/30/60/60 for train/val/test_seen/test_unseen. Sampling is seeded per game and spreads picks across runs first. The same seed gives identical results (tested), and a cache hit gives the same numbers as a fresh extract.

## Results (default scale)
<!-- gbench:results:begin -->
_Generated by `python3 -m gbench report` from runs/v11_default_seed*/results.json (seeds [0, 1, 2]); mean ± sample sd over seeds. Full per-run detail, the large-scale run and per-perturbation numbers are in RESULTS.md._

#### T2_sprite_sem (default scale)

| method | seen acc | seen macro_f1 | unseen acc | unseen macro_f1 | unseen-games acc | unseen-games macro_f1 |
|---|---|---|---|---|---|---|
| random | 0.065 ± 0.003 | 0.052 ± 0.004 | 0.072 ± 0.001 | 0.059 ± 0.002 | 0.069 ± 0.007 | 0.055 ± 0.007 |
| majority | 0.155 ± 0.005 | 0.019 ± 0.001 | 0.172 ± 0.004 | 0.021 ± 0.000 | 0.171 ± 0.004 | 0.021 ± 0.000 |
| hist_knn_k1 | 0.548 ± 0.016 | 0.470 ± 0.017 | 0.311 ± 0.007 | 0.213 ± 0.007 | 0.285 ± 0.010 | 0.166 ± 0.009 |
| hist_knn_k10 | 0.491 ± 0.007 | 0.400 ± 0.002 | 0.311 ± 0.013 | 0.200 ± 0.015 | 0.314 ± 0.012 | 0.171 ± 0.007 |
| phash_knn_k1 | 0.469 ± 0.002 | 0.408 ± 0.009 | 0.313 ± 0.004 | 0.257 ± 0.012 | 0.293 ± 0.009 | 0.191 ± 0.022 |
| logreg_size_only | 0.101 ± 0.017 | 0.070 ± 0.004 | 0.110 ± 0.008 | 0.091 ± 0.004 | 0.128 ± 0.004 | 0.102 ± 0.008 |
| size_knn_k10 | 0.290 ± 0.008 | 0.210 ± 0.019 | 0.213 ± 0.013 | 0.138 ± 0.007 | 0.195 ± 0.022 | 0.105 ± 0.018 |
| logreg_hist+simple | 0.429 ± 0.011 | 0.385 ± 0.014 | 0.279 ± 0.005 | 0.225 ± 0.010 | 0.298 ± 0.009 | 0.209 ± 0.011 |

#### T2_sprite_sem_occ (default scale)

| method | seen acc | seen macro_f1 | unseen acc | unseen macro_f1 | unseen-games acc | unseen-games macro_f1 |
|---|---|---|---|---|---|---|
| random | 0.068 ± 0.009 | 0.054 ± 0.008 | 0.073 ± 0.003 | 0.060 ± 0.000 | 0.077 ± 0.007 | 0.062 ± 0.007 |
| majority | 0.156 ± 0.003 | 0.019 ± 0.000 | 0.173 ± 0.002 | 0.021 ± 0.000 | 0.174 ± 0.003 | 0.021 ± 0.000 |
| hist_knn_k1 | 0.555 ± 0.007 | 0.471 ± 0.016 | 0.319 ± 0.004 | 0.217 ± 0.005 | 0.293 ± 0.011 | 0.169 ± 0.017 |
| hist_knn_k10 | 0.492 ± 0.010 | 0.395 ± 0.014 | 0.317 ± 0.009 | 0.202 ± 0.010 | 0.321 ± 0.012 | 0.175 ± 0.010 |
| phash_knn_k1 | 0.488 ± 0.004 | 0.431 ± 0.011 | 0.319 ± 0.004 | 0.265 ± 0.013 | 0.294 ± 0.002 | 0.196 ± 0.007 |
| logreg_size_only | 0.106 ± 0.019 | 0.075 ± 0.013 | 0.110 ± 0.012 | 0.093 ± 0.010 | 0.121 ± 0.007 | 0.096 ± 0.013 |
| size_knn_k10 | 0.271 ± 0.001 | 0.182 ± 0.009 | 0.231 ± 0.011 | 0.154 ± 0.006 | 0.220 ± 0.013 | 0.140 ± 0.012 |
| logreg_hist+simple | 0.437 ± 0.014 | 0.400 ± 0.015 | 0.284 ± 0.003 | 0.225 ± 0.013 | 0.299 ± 0.001 | 0.202 ± 0.014 |

#### T6_resleak (default scale)

| method | seen acc | seen macro_f1 | seen bal_acc | unseen acc | unseen macro_f1 | unseen bal_acc | unseen-games acc | unseen-games macro_f1 | unseen-games bal_acc |
|---|---|---|---|---|---|---|---|---|---|
| random | 0.337 ± 0.002 | 0.283 ± 0.002 | 0.337 ± 0.008 | 0.339 ± 0.005 | 0.260 ± 0.004 | 0.337 ± 0.010 | 0.331 ± 0.007 | 0.249 ± 0.003 | 0.318 ± 0.015 |
| majority | 0.706 ± 0.001 | 0.276 ± 0.000 | 0.333 ± 0.000 | 0.778 ± 0.004 | 0.292 ± 0.001 | 0.333 ± 0.000 | 0.786 ± 0.004 | 0.293 ± 0.001 | 0.333 ± 0.000 |
| hist_knn_k1 | 0.778 ± 0.009 | 0.677 ± 0.004 | 0.654 ± 0.007 | 0.705 ± 0.002 | 0.387 ± 0.021 | 0.387 ± 0.023 | 0.695 ± 0.004 | 0.380 ± 0.018 | 0.388 ± 0.026 |
| hist_knn_k10 | 0.783 ± 0.004 | 0.668 ± 0.006 | 0.644 ± 0.004 | 0.714 ± 0.014 | 0.364 ± 0.006 | 0.362 ± 0.007 | 0.707 ± 0.016 | 0.367 ± 0.008 | 0.363 ± 0.009 |
| phash_knn_k1 | 0.735 ± 0.010 | 0.585 ± 0.019 | 0.565 ± 0.014 | 0.709 ± 0.006 | 0.349 ± 0.004 | 0.350 ± 0.004 | 0.721 ± 0.007 | 0.350 ± 0.005 | 0.351 ± 0.004 |
| logreg_size_only | 0.336 ± 0.329 | 0.149 ± 0.116 | 0.333 ± 0.000 | 0.336 ± 0.395 | 0.140 ± 0.139 | 0.333 ± 0.000 | 0.335 ± 0.400 | 0.140 ± 0.140 | 0.333 ± 0.000 |
| size_knn_k10 | 0.706 ± 0.001 | 0.276 ± 0.000 | 0.333 ± 0.000 | 0.778 ± 0.004 | 0.292 ± 0.001 | 0.333 ± 0.000 | 0.786 ± 0.004 | 0.293 ± 0.001 | 0.333 ± 0.000 |
| native_size_logreg | 0.910 ± 0.028 | 0.878 ± 0.031 | 0.919 ± 0.042 | 0.919 ± 0.007 | 0.875 ± 0.008 | 0.948 ± 0.009 | 0.919 ± 0.008 | 0.904 ± 0.011 | 0.956 ± 0.012 |
| native_size_knn_k10 | 0.989 ± 0.001 | 0.985 ± 0.002 | 0.983 ± 0.001 | 0.994 ± 0.001 | 0.981 ± 0.005 | 0.985 ± 0.001 | 0.995 ± 0.002 | 0.990 ± 0.002 | 0.989 ± 0.001 |
| logreg_hist+simple | 0.748 ± 0.010 | 0.669 ± 0.008 | 0.713 ± 0.006 | 0.663 ± 0.013 | 0.472 ± 0.016 | 0.520 ± 0.022 | 0.664 ± 0.026 | 0.494 ± 0.023 | 0.578 ± 0.026 |

#### T6_resleak_stretch (default scale)

| method | seen acc | seen macro_f1 | seen bal_acc | unseen acc | unseen macro_f1 | unseen bal_acc | unseen-games acc | unseen-games macro_f1 | unseen-games bal_acc |
|---|---|---|---|---|---|---|---|---|---|
| random | 0.337 ± 0.002 | 0.283 ± 0.002 | 0.337 ± 0.008 | 0.339 ± 0.005 | 0.260 ± 0.004 | 0.337 ± 0.010 | 0.331 ± 0.007 | 0.249 ± 0.003 | 0.318 ± 0.015 |
| majority | 0.706 ± 0.001 | 0.276 ± 0.000 | 0.333 ± 0.000 | 0.778 ± 0.004 | 0.292 ± 0.001 | 0.333 ± 0.000 | 0.786 ± 0.004 | 0.293 ± 0.001 | 0.333 ± 0.000 |
| hist_knn_k1 | 0.736 ± 0.002 | 0.629 ± 0.005 | 0.603 ± 0.007 | 0.691 ± 0.015 | 0.399 ± 0.040 | 0.403 ± 0.043 | 0.679 ± 0.016 | 0.394 ± 0.045 | 0.411 ± 0.058 |
| hist_knn_k10 | 0.746 ± 0.005 | 0.626 ± 0.002 | 0.587 ± 0.003 | 0.701 ± 0.011 | 0.371 ± 0.040 | 0.369 ± 0.034 | 0.686 ± 0.009 | 0.369 ± 0.047 | 0.372 ± 0.049 |
| phash_knn_k1 | 0.686 ± 0.007 | 0.533 ± 0.024 | 0.527 ± 0.023 | 0.666 ± 0.008 | 0.337 ± 0.012 | 0.337 ± 0.013 | 0.672 ± 0.012 | 0.338 ± 0.017 | 0.338 ± 0.016 |
| logreg_size_only | 0.336 ± 0.329 | 0.149 ± 0.116 | 0.333 ± 0.000 | 0.336 ± 0.395 | 0.140 ± 0.139 | 0.333 ± 0.000 | 0.335 ± 0.400 | 0.140 ± 0.140 | 0.333 ± 0.000 |
| size_knn_k10 | 0.706 ± 0.001 | 0.276 ± 0.000 | 0.333 ± 0.000 | 0.778 ± 0.004 | 0.292 ± 0.001 | 0.333 ± 0.000 | 0.786 ± 0.004 | 0.293 ± 0.001 | 0.333 ± 0.000 |
| native_size_logreg | 0.910 ± 0.028 | 0.878 ± 0.031 | 0.919 ± 0.042 | 0.919 ± 0.007 | 0.875 ± 0.008 | 0.948 ± 0.009 | 0.919 ± 0.008 | 0.904 ± 0.011 | 0.956 ± 0.012 |
| native_size_knn_k10 | 0.989 ± 0.001 | 0.985 ± 0.002 | 0.983 ± 0.001 | 0.994 ± 0.001 | 0.981 ± 0.005 | 0.985 ± 0.001 | 0.995 ± 0.002 | 0.990 ± 0.002 | 0.989 ± 0.001 |
| logreg_hist+simple | 0.679 ± 0.040 | 0.617 ± 0.034 | 0.671 ± 0.029 | 0.610 ± 0.041 | 0.443 ± 0.030 | 0.506 ± 0.024 | 0.599 ± 0.031 | 0.457 ± 0.025 | 0.575 ± 0.035 |

#### T3_game_retrieval (default scale)

| method | seen R@1 | seen mAP | unseen R@1 | unseen mAP | unseen-games R@1 | unseen-games mAP |
|---|---|---|---|---|---|---|
| random | 0.003 ± 0.000 | 0.003 ± 0.000 | 0.007 ± 0.001 | 0.009 ± 0.000 | 0.008 ± 0.004 | 0.013 ± 0.000 |
| hist_hellinger | 0.607 ± 0.001 | 0.409 ± 0.002 | 0.619 ± 0.005 | 0.421 ± 0.005 | 0.816 ± 0.006 | 0.609 ± 0.008 |
| phash_hamming | 0.373 ± 0.004 | 0.220 ± 0.002 | 0.321 ± 0.002 | 0.161 ± 0.001 | 0.451 ± 0.005 | 0.230 ± 0.003 |
| dhash_hamming | 0.387 ± 0.007 | 0.244 ± 0.004 | 0.305 ± 0.007 | 0.149 ± 0.003 | 0.430 ± 0.007 | 0.214 ± 0.001 |
| simple_cosine | 0.598 ± 0.006 | 0.392 ± 0.001 | 0.558 ± 0.004 | 0.349 ± 0.003 | 0.737 ± 0.010 | 0.508 ± 0.007 |

#### T2 occlusion filter: what it removed (entities passing the size and class filters, summed over splits and seeds)

| source | considered | carry a visibility/occlusion field | vanished | truncated | low_visible_frac | occluded_flag | occluded_frac | off_frame | kept |
|---|---|---|---|---|---|---|---|---|---|
| pygame | 121,305 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| web | 117,378 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| threejs | 85,894 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| roguelike | 81,443 | 0% | 0 | 0 | 0 | 0 | 0 | 307 | 99.6% |
| arcade | 72,563 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| godot | 43,419 | 4% | 0 | 0 | 0 | 0 | 435 | 0 | 99.0% |
| synth | 38,250 | 100% | 634 | 3,506 | 2,331 | 0 | 0 | 0 | 83.1% |
| pyxel | 32,222 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| kaplay | 5,529 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| love | 4,742 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| nethack | 4,213 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| luanti | 3,969 | 100% | 0 | 0 | 0 | 823 | 0 | 0 | 79.3% |
| raylib | 706 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| pyglet | 286 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| ursina | 272 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| panda3d | 195 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| kivy | 177 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| tic80 | 90 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| pgzero | 6 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| renpy | 6 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |

<!-- gbench:results:end -->

## Class-map quirks that affect T2 (full tables in `CLASSMAP_AUDIT.md`, regenerate with `python3 -m gbench classmap`)
T2 labels are the shared `sem` classes from `/workspace/gamedata/ALL/class_map.json`. They are exact copies of the map, not a visual ground truth. Counts below are dataset-wide box counts stored in the map (verified against it on 2026-11-25).
- **Whole suits mapped differently (synth).** Every hearts card class (`card_hearts`, `card_hearts_a/j/k/q`, ..., 91,106 boxes) maps to `item`, while diamonds (45,460), spades (45,710) and clubs (44,188) map to `card`. The same cards look alike, so a classifier is punished for being visually right. Joker and card backs map to `card`.
- **Colour variants of `character` (synth).** The bare class `character` (138,754 boxes) maps to `character`, but the coloured variants `character_<colour>_<colour>` (81,122 boxes) map to `prop`.
- **Other mixed families (synth).** `particle_*`: prop 54,327 / fx 28,264 / item 10,248; `ball_*`: piece 113,945 / enemy 144 (`ball_lightning`, `ball_python`); `piece_of_ambrosia` is an `item` among 235,504 `piece` boxes. The same raw name differs by source: `tree` is `prop` in synth (25,773) but `decor` in roguelike (253,699) and web (52,356); `cloud` is `item` in synth (13,534) but `decor` in kaplay; `rock` is `item` in nethack (40,622) but `prop` in roguelike and synth.
- **Package-style names group unrelated things (pyxel).** Most pyxel classes are sprite-sheet cells named `<game>/img<bank>_<x>_<y>_<w>x<h>`; the map assigns them per game by rule, and 40 % of pyxel boxes are `tile`. Tiny 8×8 `tile` crops are hard to tell apart from other classes by colour alone.
- **`unknown` is dropped from T2, so some sources barely appear.** Share of boxes mapped to `unknown`: pgzero 100 %, cocos2d 100 %, tic80 99 %, renpy 98 %, panda3d 90 %, love 88 %, ursina 86 %, pyglet 81 %, kaplay 66 %, arcade 61 %, raylib 58 %, kivy 55 %, godot 19 %, web 22 %, pyxel 23 %. Synth, roguelike, nethack and luanti have almost none.
- **Single-class sources.** luanti is 99 % `enemy`; pygame is 77 % `tile`; threejs is 88 % `prop`; nethack and roguelike classes come from game rules (kind=object, kind=unit). A T2 score is dominated by synth, roguelike, pygame, godot and web crops.
- **The occlusion filter cannot see most sources.** Boxes are not occlusion-tested for engine captures (`gamedata/DATASET.md`). Only synth (`vanished`, `truncated`, `visible_frac` / `visibility`), godot 3D (`occluded` fraction, present on a small share of entities) and luanti (`occluded` flag) carry a usable field; the per-source table in RESULTS.md shows the share of entities with a field and what was dropped. The `vis` field of pygame/pyxel/threejs/kaplay/love is deliberately not used: its meaning differs between engine hooks (some are on-screen share of the box, some of the frame) and cannot be read as occlusion.

## Known limits
- **Samples, not full splits.** Default scale scores about 3.4k–3.8k frames per eval split (≤ 30 per game). Seed-to-seed sd is reported; small sources (kivy, renpy, pgzero, raylib) contribute few test frames, so per-class F1 for them is noisy.
- **unseen ≠ unseen games for synth and roguelike.** Their test_unseen frames come from games whose names are in train (held-out genre, tileset/font or seed). Quote unseen-games for new-game generalisation. For roguelike render hold-outs, the datasheet notes most frames share game states with train under another font.
- **T1 shortcut: removed from the pixels, still present in the metadata.** On raw T1, 10-NN on frame width/height alone beat every image baseline on unseen-games (macro-F1 0.442 vs 0.389 for the best image model; seed-mean of the default runs). On T1-norm the model sees a constant 256×256, so the size-only controls fall to the class prior (balanced accuracy 0.053 on unseen-games, chance 0.050; checked in every run's `shortcut_check`). That is true by construction, so it only shows the size column is gone from the inputs. What it does not show: (a) the original size is still strongly predictive (`native_size_knn_k10`, balanced accuracy 0.474 on unseen-games), so any model given the metadata, or any pipeline that resizes unevenly, can still exploit it; (b) resizing leaves traces (low-resolution frames upscaled to 256×256 are blurrier or blockier than natively large ones), so some resolution information may survive in the pixels and nothing here measures it. Image baselines moved little between raw and normalised (best logreg unseen-games macro-F1 0.389 raw, 0.379 letterbox, 0.375 stretch, sd about 0.01), which says they were not using size, only that the old control was the shortcut. Letterbox bars hurt the histogram kNN (10-NN unseen-games balanced accuracy 0.394 raw, 0.325 letterbox, 0.390 stretch); stretch is the cleaner variant for histogram features, letterbox keeps the aspect cue in the bars.
- **T2 labels inherit class_map quirks.** `sem` comes from `ALL/class_map.json` rules per source (e.g. synth `card_hearts*` maps to `item` while other suits map to `card`). Occlusion and visibility are not filtered (synth records carry a `visibility` field that is ignored), so some crops are partly covered. `unknown` is dropped, which removes most of cocos2d, pgzero, tic80, renpy, love, panda3d and ursina from T2.
- **T3/T4 near-identical neighbours.** Consecutive frames of one run are often near-duplicates. T3 removes the query's own run from the gallery for the unseen splits; T3-seen queries vs the train gallery cannot hit their own run (runs are split-disjoint). In T4 other frames of the same run remain in the gallery as hard negatives, which caps R@1 below 1 for static scenes.
- **T2 occlusion filter touches few crops.** It removes 16.9 % of synth entities (truncated 3,506, low visible fraction 2,331, vanished 634 of 38,250), 20.7 % of luanti, 1.0 % of godot (3D occluded fraction) and under 0.1 % elsewhere; 17 of the 20 sources with crops have no usable visibility field (only synth, luanti and a few godot 3D entities do). Differences between T2 and T2-occ are within seed noise on the aggregate scores (e.g. pHash 1-NN macro-F1 on unseen 0.232 vs 0.240), so the filter is a hygiene option, not a score changer, and it cannot clean engine captures (pygame, web, arcade, ...) whose boxes are not occlusion-tested.
- **T4 hard tier is hard for hashes in different ways.** A 15 % crop per side drops pHash/dHash R@1 to about 0.03 (DCT hash of a shifted frame) while the colour-histogram and simple-feature rankers keep 0.46 to 0.50; a colour cast drops the histogram to 0.01. The combined perturbation is the hardest (best method 0.31 R@1). The tiers use the same query frames, so mild and hard are directly comparable.
- **Columns are not comparable across galleries.** T3-seen ranks against the train sample (439 games), while unseen / unseen-games rank inside a smaller split (125 / 87 games), so higher unseen-games R@1 does not mean unseen games are easier. Compare methods within a column.
- **T4 perturbations are synthetic** and mild (four fixed kinds); they do not model re-encoding chains, overlays or palette swaps.
- **T5 NMI is inflated** when k is large relative to n (random assignment already scores high NMI); ARI is chance-corrected and is the headline.
- **Baselines only.** Nothing here is a model result for the game labeler. Numbers come only from `runs/*/results.json` and `run.log`; RESULTS.md and the block above are generated by code.
- Images are decoded with Pillow; JPEG frames use draft decoding (≤ 512 px side) for frame-level features, crops are cut from full-resolution decodes.
