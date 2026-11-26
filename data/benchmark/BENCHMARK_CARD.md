# gbench datasheet (benchmark v1.3)

CPU-only evaluation suite for the cleaned game-asset dataset `clean_v1`. No pretrained weights, no GPU, no Hugging Face. Every number in RESULTS.md is copied from a `results.json` / `run.log`. Training is on hold.

- **gbench** 0.4.0 / **bench** 1.3 (2026-11-25, America/Chicago)
- **Dataset:** `/workspace/gamedata-work/clean_v1` (read-only). Images under `/workspace/gamedata`. Do not modify `clean_v1` or `/workspace/gamedata/ALL/class_map.json`.
- **Code:** `/workspace/gamedata-work/benchmark`

## Splits

Eval splits: `train`, `val`, `test_seen`, `test_unseen`. `reserve` and `licence_review` are excluded. Labels come from engine/generator state, not from a trained model.

| Split | Meaning |
|---|---|
| test_seen | Held-back runs of training games |
| test_unseen | Released test_unseen: whole held-out games, plus unseen genre/render/seed variants of synth and roguelike (38 game names can appear in both train and test_unseen by design) |
| test_unseen_games | Strict subset of test_unseen whose `(source, game)` never appears in train/val/test_seen. Use this for new-game claims. |

Default-scale per-game caps: train 40, val 15, test_seen 30, test_unseen 30 frames. Default seeds: 0, 1, 2. A large-scale seed 0 exists only for v1.

## Tasks

| Task | What it measures |
|---|---|
| T1_source_id | Frame → engine/source (raw pixels; v1). Size-only is a known shortcut. |
| T1_norm / T1_norm_stretch | Same labels after a named normalisation to 256×256 (letterbox or stretch, plus optional anti-leak extras). Size-only must be near chance. |
| T2_sprite_sem / T2_sprite_sem_occ | Entity crop → shared semantic class; optional occlusion filter. Uses the class map. |
| T3_game_retrieval | Same-game retrieval (no class labels). |
| T4_near_dup | Near-duplicate retrieval under mild and hard perturbations. |
| T5_style_cluster | Unsupervised grouping of palette/style. |
| T6_resleak / T6_resleak_stretch | From T1-norm features only, predict native max-side bucket (`<=256` / `257–512` / `>512`). Size-only must be at chance (balanced accuracy 1/3). Image features above chance mean native scale still leaks through the normalised pixels. Stretch is the cleaner leak test (no letterbox bars). |

Headline T6 / T1-cost metrics are **balanced accuracy** and **macro-F1** on `test_unseen_games`. T6 is imbalanced (~79% `max>512` on default seed 0 unseen-games), so raw accuracy is a poor headline.

## Official T1 protocol (v1.3)

**`bn64`:** letterbox every frame (including already-small ones) onto a 64×64 canvas, then upsample to 256×256 with LANCZOS in both directions. `--norm-protocol bn64` is the default in gbench 0.4.0.

Measured on default seeds 0,1,2, unseen-games, mean ± sample sd (chance T6 bal_acc = 0.333):

| Protocol | T6 letterbox logreg bal_acc | T6 letterbox hist_k1 bal_acc | T6 stretch logreg bal_acc | T6 stretch hist_k1 bal_acc | T1 logreg macro-F1 | T1 logreg bal_acc | T1 hist_k1 macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| letterbox-256 (v1.1 T1 / v1.2 T6) | 0.578 ± 0.026 | 0.388 ± 0.026 | 0.575 ± 0.035 | 0.411 ± 0.058 | 0.379 ± 0.011 | 0.420 ± 0.011 | 0.324 ± 0.011 |
| **bn64 (official)** | **0.460 ± 0.025** | 0.415 ± 0.054 | 0.514 ± 0.029 | 0.412 ± 0.062 | **0.368 ± 0.030** | 0.379 ± 0.032 | 0.320 ± 0.007 |
| bn96 | 0.467 ± 0.009 | 0.400 ± 0.020 | 0.538 ± 0.051 | 0.420 ± 0.050 | 0.359 ± 0.008 | 0.367 ± 0.006 | 0.326 ± 0.022 |
| bn64_blur (Gaussian r=1.0 at 64) | 0.535 ± 0.011 | 0.411 ± 0.040 | 0.553 ± 0.019 | 0.419 ± 0.054 | 0.352 ± 0.009 | 0.387 ± 0.027 | 0.254 ± 0.013 |
| bn64_jpeg (JPEG q50 at 64) | 0.494 ± 0.018 | 0.449 ± 0.028 | 0.471 ± 0.027 | 0.424 ± 0.080 | 0.346 ± 0.019 | 0.354 ± 0.026 | 0.313 ± 0.005 |

**Tradeoff:** `bn64` gives the largest drop in T6 letterbox logreg leak (0.578 → 0.460) with the smallest T1 cost among the anti-leak variants (logreg macro-F1 0.379 → 0.368, within seed noise; hist almost flat). The leak is **reduced, not removed** — 0.460 is still clearly above chance. `bn64_jpeg` has a lower stretch-logreg leak (0.471) but a larger T1 drop and a worse letterbox hist leak. `bn64_blur` barely helps leak and damages T1 hist. Size-only controls stayed at chance on every protocol and seed. Use `--norm-protocol letterbox` for the v1.2 path.

## Known shortcuts and leaks

| Issue | Status (measured) |
|---|---|
| T1 raw size shortcut | Present in v1: size 10-NN beat image baselines on unseen-games. |
| T1-norm size column | Closed: after 256×256 letterbox/stretch (and all v1.3 protocols), size-only balanced accuracy equals chance / majority. |
| Native-size metadata | Still predictive if you cheat (`native_size_knn_k10`). This control is not a model-visible feature. |
| T6 scale traces in T1-norm pixels | Found in v1.2 (letterbox logreg bal_acc 0.578 ± 0.026, stretch 0.575 ± 0.035, unseen-games). Reduced under official `bn64` (0.460 ± 0.025 / 0.514 ± 0.029) but still above chance (0.333). Letterbox hist_k1 was already close to 0.39 and did not improve. |
| Letterbox aspect bars | Stretch is the cleaner T6 test. Official T1 still letterboxes (aspect may remain in the bars). |
| 38 synth/roguelike names in train and test_unseen | By design (held-out kind, not whole game). Use `test_unseen_games` for new-game claims. |

## Class-map versions

| Map | Path | Use |
|---|---|---|
| v1 | `class_map_v1.json` (sha256 `b3b2437e7a694b3b90dc47454ca970ef5b241c0f40fac0ba5dcee42c30a07eec`, snapshot of `ALL/class_map.json`, content unchanged) | v1 / v1.1 T2 |
| v1.2 | `class_map_v1.2.json` (sha256 `e60c0e0e0f2c3596e2fcff8fb592adf03c486bcfd027f0ee00c4fcb2e973a1f9`) | v1.2 and v1.3 T2. 20 classes / 186,118 boxes remapped with source-metadata evidence (`card_hearts*` item→card, `character_*` prop→character, `tree_large`/`tree_small` prop→decor). synth `tree` and `dead_tree` stay prop. See `CLASSMAP_AUDIT.md`. |
| Lookup | v1.2 also prefers `game/raw` keys over the bare class (rescues existing overrides; not a new mapping). | |

v1.3 does not change the class map.

## How to reproduce

From `/workspace/gamedata-work/benchmark`, on CPU, no network required after the dataset is in place:

```bash
# official T1 + leak probe, one seed
python3 -m gbench --class-map class_map_v1.2.json run \
  --scale default --seed 0 --norm-protocol bn64 \
  --name v13_bn64_default_seed0 --resume \
  --tasks T1_norm T6_resleak T6_resleak_stretch

# all four anti-leak protocols, seeds 0,1,2
./run_v13.sh

# rebuild RESULTS.md / the generated block in BENCHMARK.md
python3 -m gbench report
```

Other protocols: `--norm-protocol letterbox|stretch|bn96|bn64_blur|bn64_jpeg`. Feature caches under `features/` are rebuildable; never delete `clean_v1` or `runs/*/results.json`. Frozen prior versions: `RESULTS_v1.md`, `RESULTS_v11.md`, `RESULTS_v12.md` and the matching `runs_*_manifest.sha256`. Tests: `python3 -m pytest -q tests`.

Nothing in this suite is published; training stays on hold.
