# gbench — CPU evaluation benchmark for the clean_v1 game-frame dataset

Owner: Jordan Newman, OmniSpace Technologies LLC. Benchmark v1.1 (gbench 0.2.0), 2026-11-25. v1 (gbench 0.1.0) is kept for comparison: `BENCHMARK_v1.md`, `RESULTS_v1.md`, `runs/default_seed{0,1,2}`, `runs/large_seed0` (sha256 in `runs_v1_manifest.sha256`); nothing in them was touched.

## What changed in v1.1
1. **T1-norm** (`T1_norm`, `T1_norm_stretch`): every frame is resized to 256×256 before any feature is computed (letterboxed with black bars, or stretched with no bars). The size-only control sees the size the model sees (constant) and is checked against chance in every run (`shortcut_check` in results.json). The native frame size is kept as a separate, clearly labelled metadata control (`native_size_*`).
2. **T2 occlusion filter** (`T2_sprite_sem_occ`, option `--occ-min-visible`, `--occ-min-in-frame`): reported next to unfiltered T2 in every run, with a per-source table of what it removed. The class-map quirks are documented below and in `CLASSMAP_AUDIT.md`.
3. **T4 tiers**: mild (unchanged, pooled `mild_all` = v1's `all`) and hard (six stronger perturbations, pooled `hard_all`).
4. v1 tasks T1, T2, T3, T5 and the mild T4 are unchanged; the report prints a protocol check that counts the cells identical between v1 and v1.1 runs.
Scope: evaluation only. No model is trained on the dataset here (training stays on hold and, when it happens, runs on the DGX Sparks with Jordan's yes). The "learned" baseline is a small numpy logistic regression on hand-made features, fitted on the train sample inside each run. No pretrained weights, no Hugging Face, no GPU.

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

#### T1 raw vs normalised, unseen-games (default scale)

| method | raw v1 macro_f1 | raw v1 bal_acc | norm letterbox macro_f1 | norm letterbox bal_acc | norm stretch macro_f1 | norm stretch bal_acc |
|---|---|---|---|---|---|---|
| hist_knn_k1 | 0.351 ± 0.010 | 0.364 ± 0.003 | 0.324 ± 0.011 | 0.339 ± 0.009 | 0.354 ± 0.014 | 0.368 ± 0.006 |
| hist_knn_k10 | 0.369 ± 0.006 | 0.394 ± 0.008 | 0.318 ± 0.008 | 0.325 ± 0.006 | 0.363 ± 0.005 | 0.390 ± 0.006 |
| logreg_hist+simple | 0.389 ± 0.016 | 0.418 ± 0.022 | 0.379 ± 0.011 | 0.420 ± 0.011 | 0.375 ± 0.013 | 0.407 ± 0.010 |
| logreg_size_only | 0.161 ± 0.007 | 0.351 ± 0.004 | 0.002 ± 0.003 | 0.053 ± 0.000 | 0.002 ± 0.003 | 0.053 ± 0.000 |
| majority | 0.014 ± 0.000 | 0.053 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| phash_knn_k1 | 0.144 ± 0.007 | 0.151 ± 0.006 | 0.166 ± 0.009 | 0.177 ± 0.005 | 0.151 ± 0.007 | 0.156 ± 0.006 |
| random | 0.043 ± 0.004 | 0.047 ± 0.008 | 0.043 ± 0.004 | 0.047 ± 0.008 | 0.043 ± 0.004 | 0.047 ± 0.008 |
| size_knn_k10 | 0.442 ± 0.038 | 0.474 ± 0.045 | 0.014 ± 0.000 | 0.053 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| native_size_knn_k10 | – | – | 0.442 ± 0.038 | 0.474 ± 0.045 | 0.442 ± 0.038 | 0.474 ± 0.045 |
| native_size_logreg | – | – | 0.161 ± 0.007 | 0.351 ± 0.004 | 0.161 ± 0.007 | 0.351 ± 0.004 |

#### T1 raw vs normalised, seen (default scale)

| method | raw v1 macro_f1 | raw v1 bal_acc | norm letterbox macro_f1 | norm letterbox bal_acc | norm stretch macro_f1 | norm stretch bal_acc |
|---|---|---|---|---|---|---|
| hist_knn_k1 | 0.709 ± 0.011 | 0.749 ± 0.000 | 0.692 ± 0.009 | 0.743 ± 0.003 | 0.712 ± 0.017 | 0.753 ± 0.002 |
| hist_knn_k10 | 0.641 ± 0.001 | 0.732 ± 0.011 | 0.613 ± 0.006 | 0.709 ± 0.002 | 0.642 ± 0.003 | 0.733 ± 0.009 |
| logreg_hist+simple | 0.687 ± 0.024 | 0.738 ± 0.028 | 0.640 ± 0.025 | 0.703 ± 0.036 | 0.667 ± 0.024 | 0.726 ± 0.028 |
| logreg_size_only | 0.158 ± 0.018 | 0.412 ± 0.013 | 0.001 ± 0.001 | 0.056 ± 0.000 | 0.001 ± 0.001 | 0.056 ± 0.000 |
| majority | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 |
| phash_knn_k1 | 0.398 ± 0.005 | 0.417 ± 0.002 | 0.389 ± 0.008 | 0.409 ± 0.008 | 0.399 ± 0.004 | 0.417 ± 0.003 |
| random | 0.041 ± 0.001 | 0.045 ± 0.004 | 0.041 ± 0.001 | 0.045 ± 0.004 | 0.041 ± 0.001 | 0.045 ± 0.004 |
| size_knn_k10 | 0.539 ± 0.028 | 0.612 ± 0.066 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 |
| native_size_knn_k10 | – | – | 0.539 ± 0.028 | 0.612 ± 0.066 | 0.539 ± 0.028 | 0.612 ± 0.066 |
| native_size_logreg | – | – | 0.158 ± 0.018 | 0.412 ± 0.013 | 0.158 ± 0.018 | 0.412 ± 0.013 |

#### T1_source_id (default scale)

| method | seen acc | seen macro_f1 | seen bal_acc | unseen acc | unseen macro_f1 | unseen bal_acc | unseen-games acc | unseen-games macro_f1 | unseen-games bal_acc |
|---|---|---|---|---|---|---|---|---|---|
| random | 0.050 ± 0.003 | 0.041 ± 0.001 | 0.045 ± 0.004 | 0.051 ± 0.005 | 0.039 ± 0.004 | 0.048 ± 0.007 | 0.051 ± 0.003 | 0.043 ± 0.004 | 0.047 ± 0.008 |
| majority | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.053 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| hist_knn_k1 | 0.785 ± 0.003 | 0.709 ± 0.011 | 0.749 ± 0.000 | 0.488 ± 0.010 | 0.368 ± 0.009 | 0.383 ± 0.002 | 0.395 ± 0.013 | 0.351 ± 0.010 | 0.364 ± 0.003 |
| hist_knn_k10 | 0.723 ± 0.012 | 0.641 ± 0.001 | 0.732 ± 0.011 | 0.443 ± 0.006 | 0.366 ± 0.006 | 0.411 ± 0.007 | 0.416 ± 0.009 | 0.369 ± 0.006 | 0.394 ± 0.008 |
| phash_knn_k1 | 0.444 ± 0.003 | 0.398 ± 0.005 | 0.417 ± 0.002 | 0.199 ± 0.004 | 0.139 ± 0.006 | 0.162 ± 0.005 | 0.194 ± 0.001 | 0.144 ± 0.007 | 0.151 ± 0.006 |
| logreg_size_only | 0.183 ± 0.025 | 0.158 ± 0.018 | 0.412 ± 0.013 | 0.153 ± 0.007 | 0.134 ± 0.008 | 0.351 ± 0.005 | 0.176 ± 0.006 | 0.161 ± 0.007 | 0.351 ± 0.004 |
| size_knn_k10 | 0.602 ± 0.012 | 0.539 ± 0.028 | 0.612 ± 0.066 | 0.611 ± 0.016 | 0.435 ± 0.037 | 0.478 ± 0.044 | 0.550 ± 0.020 | 0.442 ± 0.038 | 0.474 ± 0.045 |
| logreg_hist+simple | 0.753 ± 0.003 | 0.687 ± 0.024 | 0.738 ± 0.028 | 0.508 ± 0.015 | 0.401 ± 0.016 | 0.433 ± 0.020 | 0.439 ± 0.020 | 0.389 ± 0.016 | 0.418 ± 0.022 |

#### T1_norm (default scale)

| method | seen acc | seen macro_f1 | seen bal_acc | unseen acc | unseen macro_f1 | unseen bal_acc | unseen-games acc | unseen-games macro_f1 | unseen-games bal_acc |
|---|---|---|---|---|---|---|---|---|---|
| random | 0.050 ± 0.003 | 0.041 ± 0.001 | 0.045 ± 0.004 | 0.051 ± 0.005 | 0.039 ± 0.004 | 0.048 ± 0.007 | 0.051 ± 0.003 | 0.043 ± 0.004 | 0.047 ± 0.008 |
| majority | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.053 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| hist_knn_k1 | 0.768 ± 0.003 | 0.692 ± 0.009 | 0.743 ± 0.003 | 0.455 ± 0.013 | 0.338 ± 0.011 | 0.358 ± 0.009 | 0.363 ± 0.016 | 0.324 ± 0.011 | 0.339 ± 0.009 |
| hist_knn_k10 | 0.687 ± 0.000 | 0.613 ± 0.006 | 0.709 ± 0.002 | 0.388 ± 0.007 | 0.314 ± 0.008 | 0.342 ± 0.005 | 0.366 ± 0.009 | 0.318 ± 0.008 | 0.325 ± 0.006 |
| phash_knn_k1 | 0.443 ± 0.011 | 0.389 ± 0.008 | 0.409 ± 0.008 | 0.203 ± 0.003 | 0.162 ± 0.009 | 0.188 ± 0.006 | 0.198 ± 0.001 | 0.166 ± 0.009 | 0.177 ± 0.005 |
| logreg_size_only | 0.008 ± 0.014 | 0.001 ± 0.001 | 0.056 ± 0.000 | 0.010 ± 0.017 | 0.001 ± 0.002 | 0.053 ± 0.000 | 0.015 ± 0.025 | 0.002 ± 0.003 | 0.053 ± 0.000 |
| size_knn_k10 | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.053 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| native_size_logreg | 0.183 ± 0.025 | 0.158 ± 0.018 | 0.412 ± 0.013 | 0.153 ± 0.007 | 0.134 ± 0.008 | 0.351 ± 0.005 | 0.176 ± 0.006 | 0.161 ± 0.007 | 0.351 ± 0.004 |
| native_size_knn_k10 | 0.602 ± 0.012 | 0.539 ± 0.028 | 0.612 ± 0.066 | 0.611 ± 0.016 | 0.435 ± 0.037 | 0.478 ± 0.044 | 0.550 ± 0.020 | 0.442 ± 0.038 | 0.474 ± 0.045 |
| logreg_hist+simple | 0.715 ± 0.005 | 0.640 ± 0.025 | 0.703 ± 0.036 | 0.499 ± 0.018 | 0.389 ± 0.010 | 0.437 ± 0.009 | 0.435 ± 0.021 | 0.379 ± 0.011 | 0.420 ± 0.011 |

#### T1_norm_stretch (default scale)

| method | seen acc | seen macro_f1 | seen bal_acc | unseen acc | unseen macro_f1 | unseen bal_acc | unseen-games acc | unseen-games macro_f1 | unseen-games bal_acc |
|---|---|---|---|---|---|---|---|---|---|
| random | 0.050 ± 0.003 | 0.041 ± 0.001 | 0.045 ± 0.004 | 0.051 ± 0.005 | 0.039 ± 0.004 | 0.048 ± 0.007 | 0.051 ± 0.003 | 0.043 ± 0.004 | 0.047 ± 0.008 |
| majority | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.053 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| hist_knn_k1 | 0.790 ± 0.005 | 0.712 ± 0.017 | 0.753 ± 0.002 | 0.488 ± 0.014 | 0.372 ± 0.014 | 0.386 ± 0.007 | 0.396 ± 0.021 | 0.354 ± 0.014 | 0.368 ± 0.006 |
| hist_knn_k10 | 0.725 ± 0.010 | 0.642 ± 0.003 | 0.733 ± 0.009 | 0.439 ± 0.004 | 0.360 ± 0.006 | 0.407 ± 0.007 | 0.410 ± 0.008 | 0.363 ± 0.005 | 0.390 ± 0.006 |
| phash_knn_k1 | 0.442 ± 0.002 | 0.399 ± 0.004 | 0.417 ± 0.003 | 0.201 ± 0.005 | 0.146 ± 0.005 | 0.168 ± 0.005 | 0.196 ± 0.001 | 0.151 ± 0.007 | 0.156 ± 0.006 |
| logreg_size_only | 0.008 ± 0.014 | 0.001 ± 0.001 | 0.056 ± 0.000 | 0.010 ± 0.017 | 0.001 ± 0.002 | 0.053 ± 0.000 | 0.015 ± 0.025 | 0.002 ± 0.003 | 0.053 ± 0.000 |
| size_knn_k10 | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.056 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.053 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 | 0.053 ± 0.000 |
| native_size_logreg | 0.183 ± 0.025 | 0.158 ± 0.018 | 0.412 ± 0.013 | 0.153 ± 0.007 | 0.134 ± 0.008 | 0.351 ± 0.005 | 0.176 ± 0.006 | 0.161 ± 0.007 | 0.351 ± 0.004 |
| native_size_knn_k10 | 0.602 ± 0.012 | 0.539 ± 0.028 | 0.612 ± 0.066 | 0.611 ± 0.016 | 0.435 ± 0.037 | 0.478 ± 0.044 | 0.550 ± 0.020 | 0.442 ± 0.038 | 0.474 ± 0.045 |
| logreg_hist+simple | 0.738 ± 0.004 | 0.667 ± 0.024 | 0.726 ± 0.028 | 0.495 ± 0.013 | 0.388 ± 0.013 | 0.425 ± 0.009 | 0.427 ± 0.016 | 0.375 ± 0.013 | 0.407 ± 0.010 |

#### T2_sprite_sem (default scale)

| method | seen acc | seen macro_f1 | unseen acc | unseen macro_f1 | unseen-games acc | unseen-games macro_f1 |
|---|---|---|---|---|---|---|
| random | 0.068 ± 0.008 | 0.053 ± 0.008 | 0.072 ± 0.005 | 0.060 ± 0.004 | 0.072 ± 0.004 | 0.060 ± 0.005 |
| majority | 0.124 ± 0.002 | 0.016 ± 0.000 | 0.091 ± 0.007 | 0.012 ± 0.001 | 0.125 ± 0.010 | 0.016 ± 0.001 |
| hist_knn_k1 | 0.550 ± 0.016 | 0.435 ± 0.019 | 0.309 ± 0.009 | 0.196 ± 0.011 | 0.285 ± 0.009 | 0.170 ± 0.014 |
| hist_knn_k10 | 0.488 ± 0.008 | 0.361 ± 0.005 | 0.308 ± 0.012 | 0.173 ± 0.017 | 0.311 ± 0.014 | 0.172 ± 0.019 |
| phash_knn_k1 | 0.456 ± 0.002 | 0.360 ± 0.010 | 0.309 ± 0.008 | 0.232 ± 0.009 | 0.298 ± 0.015 | 0.189 ± 0.027 |
| logreg_size_only | 0.102 ± 0.007 | 0.062 ± 0.006 | 0.108 ± 0.013 | 0.079 ± 0.016 | 0.118 ± 0.013 | 0.088 ± 0.012 |
| size_knn_k10 | 0.267 ± 0.029 | 0.175 ± 0.007 | 0.195 ± 0.023 | 0.124 ± 0.011 | 0.172 ± 0.036 | 0.106 ± 0.022 |
| logreg_hist+simple | 0.442 ± 0.005 | 0.356 ± 0.004 | 0.280 ± 0.010 | 0.209 ± 0.016 | 0.292 ± 0.019 | 0.204 ± 0.029 |

#### T2_sprite_sem_occ (default scale)

| method | seen acc | seen macro_f1 | unseen acc | unseen macro_f1 | unseen-games acc | unseen-games macro_f1 |
|---|---|---|---|---|---|---|
| random | 0.070 ± 0.006 | 0.053 ± 0.007 | 0.070 ± 0.002 | 0.057 ± 0.003 | 0.078 ± 0.007 | 0.067 ± 0.008 |
| majority | 0.132 ± 0.001 | 0.017 ± 0.000 | 0.093 ± 0.007 | 0.012 ± 0.001 | 0.127 ± 0.010 | 0.016 ± 0.001 |
| hist_knn_k1 | 0.557 ± 0.010 | 0.434 ± 0.015 | 0.315 ± 0.015 | 0.202 ± 0.016 | 0.289 ± 0.016 | 0.170 ± 0.019 |
| hist_knn_k10 | 0.487 ± 0.008 | 0.357 ± 0.009 | 0.311 ± 0.015 | 0.178 ± 0.015 | 0.312 ± 0.019 | 0.172 ± 0.017 |
| phash_knn_k1 | 0.477 ± 0.006 | 0.388 ± 0.015 | 0.316 ± 0.009 | 0.240 ± 0.013 | 0.301 ± 0.014 | 0.209 ± 0.027 |
| logreg_size_only | 0.115 ± 0.008 | 0.074 ± 0.006 | 0.113 ± 0.014 | 0.084 ± 0.015 | 0.121 ± 0.017 | 0.088 ± 0.017 |
| size_knn_k10 | 0.269 ± 0.026 | 0.191 ± 0.009 | 0.199 ± 0.029 | 0.120 ± 0.004 | 0.178 ± 0.045 | 0.103 ± 0.019 |
| logreg_hist+simple | 0.446 ± 0.009 | 0.365 ± 0.010 | 0.277 ± 0.003 | 0.202 ± 0.017 | 0.282 ± 0.010 | 0.191 ± 0.022 |

#### T3_game_retrieval (default scale)

| method | seen R@1 | seen mAP | unseen R@1 | unseen mAP | unseen-games R@1 | unseen-games mAP |
|---|---|---|---|---|---|---|
| random | 0.003 ± 0.000 | 0.003 ± 0.000 | 0.007 ± 0.001 | 0.009 ± 0.000 | 0.008 ± 0.004 | 0.013 ± 0.000 |
| hist_hellinger | 0.607 ± 0.001 | 0.409 ± 0.002 | 0.619 ± 0.005 | 0.421 ± 0.005 | 0.816 ± 0.006 | 0.609 ± 0.008 |
| phash_hamming | 0.373 ± 0.004 | 0.220 ± 0.002 | 0.321 ± 0.002 | 0.161 ± 0.001 | 0.451 ± 0.005 | 0.230 ± 0.003 |
| dhash_hamming | 0.387 ± 0.007 | 0.244 ± 0.004 | 0.305 ± 0.007 | 0.149 ± 0.003 | 0.430 ± 0.007 | 0.214 ± 0.001 |
| simple_cosine | 0.598 ± 0.006 | 0.392 ± 0.001 | 0.558 ± 0.004 | 0.349 ± 0.003 | 0.737 ± 0.010 | 0.508 ± 0.007 |

#### T4_near_dup, mild tier (default scale) (R@1; last column pooled R@1 and mAP)

| method | rescale | jpeg | bright | crop | mild_all R@1 | mild_all mAP |
|---|---|---|---|---|---|---|
| random | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.003 ± 0.001 |
| hist_hellinger | 0.913 ± 0.006 | 0.804 ± 0.016 | 0.059 ± 0.006 | 0.635 ± 0.009 | 0.603 ± 0.009 | 0.656 ± 0.007 |
| phash_hamming | 0.860 ± 0.011 | 0.848 ± 0.012 | 0.818 ± 0.007 | 0.582 ± 0.010 | 0.777 ± 0.009 | 0.841 ± 0.006 |
| dhash_hamming | 0.848 ± 0.012 | 0.819 ± 0.010 | 0.796 ± 0.012 | 0.575 ± 0.011 | 0.760 ± 0.010 | 0.824 ± 0.008 |
| simple_cosine | 0.893 ± 0.004 | 0.847 ± 0.010 | 0.579 ± 0.016 | 0.744 ± 0.016 | 0.766 ± 0.010 | 0.823 ± 0.007 |

#### T4_near_dup, hard tier (default scale) (R@1; last column pooled R@1 and mAP)

| method | h_rescale | h_jpeg | h_colour | h_crop | h_noise | h_combo | hard_all R@1 | hard_all mAP |
|---|---|---|---|---|---|---|---|---|
| random | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.002 ± 0.000 |
| hist_hellinger | 0.823 ± 0.008 | 0.597 ± 0.011 | 0.010 ± 0.004 | 0.495 ± 0.005 | 0.777 ± 0.013 | 0.040 ± 0.006 | 0.457 ± 0.004 | 0.515 ± 0.004 |
| phash_hamming | 0.855 ± 0.009 | 0.825 ± 0.011 | 0.802 ± 0.012 | 0.027 ± 0.002 | 0.827 ± 0.012 | 0.144 ± 0.008 | 0.580 ± 0.006 | 0.634 ± 0.004 |
| dhash_hamming | 0.846 ± 0.012 | 0.790 ± 0.008 | 0.779 ± 0.009 | 0.030 ± 0.003 | 0.763 ± 0.011 | 0.140 ± 0.003 | 0.558 ± 0.006 | 0.615 ± 0.004 |
| simple_cosine | 0.859 ± 0.009 | 0.790 ± 0.013 | 0.462 ± 0.016 | 0.464 ± 0.019 | 0.571 ± 0.015 | 0.310 ± 0.014 | 0.576 ± 0.010 | 0.650 ± 0.008 |

#### T5_style_cluster on test_unseen_games (default scale)

| method | NMI_game | ARI_game | purity_game | NMI_source |
|---|---|---|---|---|
| random | 0.297 ± 0.003 | 0.001 ± 0.001 | 0.087 ± 0.002 | 0.097 ± 0.004 |
| kmeans_hist | 0.824 ± 0.006 | 0.364 ± 0.052 | 0.649 ± 0.016 | 0.602 ± 0.008 |
| kmeans_simple | 0.787 ± 0.009 | 0.459 ± 0.044 | 0.599 ± 0.022 | 0.578 ± 0.010 |

#### T5_style_cluster on test_unseen (default scale)

| method | NMI_game | ARI_game | purity_game | NMI_source |
|---|---|---|---|---|
| random | 0.332 ± 0.001 | 0.000 ± 0.000 | 0.077 ± 0.001 | 0.087 ± 0.001 |
| kmeans_hist | 0.719 ± 0.009 | 0.228 ± 0.028 | 0.488 ± 0.004 | 0.495 ± 0.009 |
| kmeans_simple | 0.703 ± 0.001 | 0.323 ± 0.030 | 0.483 ± 0.011 | 0.492 ± 0.004 |

#### T2 occlusion filter: what it removed (entities passing the size and class filters, summed over splits and seeds)

| source | considered | carry a visibility/occlusion field | vanished | truncated | low_visible_frac | occluded_flag | occluded_frac | off_frame | kept |
|---|---|---|---|---|---|---|---|---|---|
| pygame | 117,507 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| web | 97,768 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| arcade | 72,563 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| roguelike | 67,483 | 0% | 0 | 0 | 0 | 0 | 0 | 84 | 99.9% |
| godot | 43,229 | 4% | 0 | 0 | 0 | 0 | 417 | 0 | 99.0% |
| threejs | 38,858 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
| synth | 38,250 | 100% | 634 | 3,506 | 2,331 | 0 | 0 | 0 | 83.1% |
| pyxel | 15,351 | 0% | 0 | 0 | 0 | 0 | 0 | 0 | 100.0% |
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
