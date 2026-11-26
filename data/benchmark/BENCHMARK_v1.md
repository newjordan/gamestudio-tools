# gbench — CPU evaluation benchmark for the clean_v1 game-frame dataset

Owner: Jordan Newman, OmniSpace Technologies LLC. Version 0.1.0, built 2026-11-25.
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
| T2_sprite_sem | entity crop cut from the exact engine box → shared `sem` class (14; `unknown` dropped) | as T1; crops ≥ 8×8 px after clipping to the frame, ≤ 3 per frame | accuracy, **macro-F1**, balanced accuracy |
| T3_game_retrieval | frame → other frames of the same game | seen: test_seen queries vs train gallery; unseen / unseen-games: leave-one-out inside the split with the query's own run removed from the gallery | R@1, R@5, R@10, **mAP** (queries without a positive are skipped and counted in `n_queries`) |
| T4_near_dup | perturbed frame → its exact original | gallery = every test_unseen sample frame; queries = a seeded subset, each under 4 perturbations: 0.5× rescale, JPEG q40, brightness ×1.25+10, 5 % border crop | **R@1**, mAP, per perturbation and pooled |
| T5_style_cluster | unsupervised palette/style grouping | k-means (k-means++, 3 inits) with k = number of games, on unseen-games and on unseen | NMI, **ARI**, purity vs game; NMI vs source |

T1 vs unseen-games is the generalisation question: does the source signature carry to games never seen? The seen − unseen gap in RESULTS.md quantifies it per method.

## Baselines (all CPU, computed on this box)
| name | tasks | what |
|---|---|---|
| random | all | seeded uniform labels / random ranking / random cluster ids |
| majority | T1, T2 | most frequent train class |
| hist_knn_k1, hist_knn_k10 | T1, T2 | 8×8×8 RGB histogram, Hellinger (sqrt-hist dot) kNN; k=10 is majority vote, ties to nearest |
| phash_knn_k1 | T1, T2 | 64-bit DCT perceptual hash, Hamming 1-NN |
| logreg_size_only, size_knn_k10 | T1, T2 | shortcut probes: logistic regression / 10-NN on log width, log height, log aspect only (frame size for T1, box size for T2) |
| logreg_hist+simple | T1, T2 | numpy softmax regression (Adam, 300 full-batch epochs, inverse-frequency class weights, L2 picked on val from 1e-4/1e-3/1e-2) on sqrt-hist + 132 simple features (4×4 RGB and 8×8 grey thumbnails, gradient stats, RGB/HSV moments, aspect, distinct-colour count) |
| hist_hellinger, phash_hamming, dhash_hamming, simple_cosine | T3, T4 | ranking by histogram similarity, pHash / dHash Hamming distance, cosine on standardised simple features |
| kmeans_hist, kmeans_simple | T5 | k-means on sqrt-hist or standardised simple features |

scikit-learn and scipy are not installed on the box, so every metric and model is plain numpy (checked against hand-computed values in the tests).

## Reproduce
```bash
cd /workspace/gamedata-work/benchmark
python3 -m gbench check                       # leak + licence checks only
python3 -m gbench run --scale default --seed 0  # ~3-5 min on 8 CPUs; writes runs/default_seed0/{run.log,results.json}
./run_all.sh                                  # the published set: default seeds 0,1,2 + large seed 0, then report
python3 -m gbench report                      # RESULTS.md + the block below, generated from results.json files
python3 -m pytest -q tests                    # harness tests on a generated toy dataset
```
Scales (per-game frame caps, so synth's 50 % share and big games do not swamp the sample): `smoke` 4/2/3/3, `default` 40/15/30/30, `large` 120/30/60/60 for train/val/test_seen/test_unseen. Sampling is seeded per game and spreads picks across runs first. The same seed gives identical results (tested), and a cache hit gives the same numbers as a fresh extract.

## Results (default scale)
<!-- gbench:results:begin -->
_Generated by `python3 -m gbench report` from runs/default_seed*/results.json (seeds [0, 1, 2]); mean ± sample sd over seeds. Full per-run detail, the large-scale run and per-perturbation numbers are in RESULTS.md._

#### T1_source_id (default scale)

| method | seen acc | seen macro_f1 | unseen acc | unseen macro_f1 | unseen-games acc | unseen-games macro_f1 |
|---|---|---|---|---|---|---|
| random | 0.050 ± 0.003 | 0.041 ± 0.001 | 0.051 ± 0.005 | 0.039 ± 0.004 | 0.051 ± 0.003 | 0.043 ± 0.004 |
| majority | 0.088 ± 0.000 | 0.009 ± 0.000 | 0.105 ± 0.000 | 0.010 ± 0.000 | 0.155 ± 0.000 | 0.014 ± 0.000 |
| hist_knn_k1 | 0.785 ± 0.003 | 0.709 ± 0.011 | 0.488 ± 0.010 | 0.368 ± 0.009 | 0.395 ± 0.013 | 0.351 ± 0.010 |
| hist_knn_k10 | 0.723 ± 0.012 | 0.641 ± 0.001 | 0.443 ± 0.006 | 0.366 ± 0.006 | 0.416 ± 0.009 | 0.369 ± 0.006 |
| phash_knn_k1 | 0.444 ± 0.003 | 0.398 ± 0.005 | 0.199 ± 0.004 | 0.139 ± 0.006 | 0.194 ± 0.001 | 0.144 ± 0.007 |
| logreg_size_only | 0.183 ± 0.025 | 0.158 ± 0.018 | 0.153 ± 0.007 | 0.134 ± 0.008 | 0.176 ± 0.006 | 0.161 ± 0.007 |
| size_knn_k10 | 0.602 ± 0.012 | 0.539 ± 0.028 | 0.611 ± 0.016 | 0.435 ± 0.037 | 0.550 ± 0.020 | 0.442 ± 0.038 |
| logreg_hist+simple | 0.753 ± 0.003 | 0.687 ± 0.024 | 0.508 ± 0.015 | 0.401 ± 0.016 | 0.439 ± 0.020 | 0.389 ± 0.016 |

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

#### T3_game_retrieval (default scale)

| method | seen R@1 | seen mAP | unseen R@1 | unseen mAP | unseen-games R@1 | unseen-games mAP |
|---|---|---|---|---|---|---|
| random | 0.003 ± 0.000 | 0.003 ± 0.000 | 0.007 ± 0.001 | 0.009 ± 0.000 | 0.008 ± 0.004 | 0.013 ± 0.000 |
| hist_hellinger | 0.607 ± 0.001 | 0.409 ± 0.002 | 0.619 ± 0.005 | 0.421 ± 0.005 | 0.816 ± 0.006 | 0.609 ± 0.008 |
| phash_hamming | 0.373 ± 0.004 | 0.220 ± 0.002 | 0.321 ± 0.002 | 0.161 ± 0.001 | 0.451 ± 0.005 | 0.230 ± 0.003 |
| dhash_hamming | 0.387 ± 0.007 | 0.244 ± 0.004 | 0.305 ± 0.007 | 0.149 ± 0.003 | 0.430 ± 0.007 | 0.214 ± 0.001 |
| simple_cosine | 0.598 ± 0.006 | 0.392 ± 0.001 | 0.558 ± 0.004 | 0.349 ± 0.003 | 0.737 ± 0.010 | 0.508 ± 0.007 |

#### T4_near_dup (default scale) (R@1; mAP for `all`)

| method | rescale | jpeg | bright | crop | all | all mAP |
|---|---|---|---|---|---|---|
| random | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.003 ± 0.001 |
| hist_hellinger | 0.913 ± 0.006 | 0.804 ± 0.016 | 0.059 ± 0.006 | 0.635 ± 0.009 | 0.603 ± 0.009 | 0.656 ± 0.007 |
| phash_hamming | 0.860 ± 0.011 | 0.848 ± 0.012 | 0.818 ± 0.007 | 0.582 ± 0.010 | 0.777 ± 0.009 | 0.841 ± 0.006 |
| dhash_hamming | 0.848 ± 0.012 | 0.819 ± 0.010 | 0.796 ± 0.012 | 0.575 ± 0.011 | 0.760 ± 0.010 | 0.824 ± 0.008 |
| simple_cosine | 0.893 ± 0.004 | 0.847 ± 0.010 | 0.579 ± 0.016 | 0.744 ± 0.016 | 0.766 ± 0.010 | 0.823 ± 0.007 |

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

<!-- gbench:results:end -->

## Known limits
- **Samples, not full splits.** Default scale scores about 3.4k–3.8k frames per eval split (≤ 30 per game). Seed-to-seed sd is reported; small sources (kivy, renpy, pgzero, raylib) contribute few test frames, so per-class F1 for them is noisy.
- **unseen ≠ unseen games for synth and roguelike.** Their test_unseen frames come from games whose names are in train (held-out genre, tileset/font or seed). Quote unseen-games for new-game generalisation. For roguelike render hold-outs, the datasheet notes most frames share game states with train under another font.
- **T1 may have shortcuts.** Engines render at typical resolutions, so frame size carries source information; the `size_knn_k10` and `logreg_size_only` rows measure how much. Measured: 10-NN on frame width/height alone beats every image baseline on unseen and unseen-games (table above). T1 therefore mostly tests resolution memorisation unless frames are resized to a common size first; a future model's T1 score must be read against `size_knn_k10`, not against random. Source is also confounded with game count: web (116 games) and godot (89) dominate the per-game-capped sample.
- **T2 labels inherit class_map quirks.** `sem` comes from `ALL/class_map.json` rules per source (e.g. synth `card_hearts*` maps to `item` while other suits map to `card`). Occlusion and visibility are not filtered (synth records carry a `visibility` field that is ignored), so some crops are partly covered. `unknown` is dropped, which removes most of cocos2d, pgzero, tic80, renpy, love, panda3d and ursina from T2.
- **T3/T4 near-identical neighbours.** Consecutive frames of one run are often near-duplicates. T3 removes the query's own run from the gallery for the unseen splits; T3-seen queries vs the train gallery cannot hit their own run (runs are split-disjoint). In T4 other frames of the same run remain in the gallery as hard negatives, which caps R@1 below 1 for static scenes.
- **Columns are not comparable across galleries.** T3-seen ranks against the train sample (439 games), while unseen / unseen-games rank inside a smaller split (125 / 87 games), so higher unseen-games R@1 does not mean unseen games are easier. Compare methods within a column.
- **T4 perturbations are synthetic** and mild (four fixed kinds); they do not model re-encoding chains, overlays or palette swaps.
- **T5 NMI is inflated** when k is large relative to n (random assignment already scores high NMI); ARI is chance-corrected and is the headline.
- **Baselines only.** Nothing here is a model result for the game labeler. Numbers come only from `runs/*/results.json` and `run.log`; RESULTS.md and the block above are generated by code.
- Images are decoded with Pillow; JPEG frames use draft decoding (≤ 512 px side) for frame-level features, crops are cut from full-resolution decodes.
