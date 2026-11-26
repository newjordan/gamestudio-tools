"""Task definitions. Each task returns {eval_split: {method: {metric: value}}}."""
import numpy as np
from . import baselines as B, metrics as M

TASKS = {
    "T1_source_id": "Frame -> engine/source (20 classes with train frames; cocos2d has none). Train on train, tune L2 on val, report test_seen and test_unseen (held-out whole games).",
    "T1_norm": "T1 with every frame letterboxed (aspect kept, black bars) to 256x256 before features; size-only control sees the model-visible size (constant) and must score near chance. Native-size controls show the metadata shortcut that is hidden.",
    "T1_norm_stretch": "T1 with every frame stretched to 256x256 (no bars, aspect lost) before features; same controls. Difference to T1_norm = leakage through letterbox bars.",
    "T2_sprite_sem": "Entity crop (from exact engine boxes) -> shared sem class (14 classes, 'unknown' dropped). Seen vs unseen games.",
    "T2_sprite_sem_occ": "T2 with the occlusion filter: drops vanished/truncated/low-visibility/occluded entities and boxes mostly outside the frame (applied to train and eval). Only sources with visibility fields (synth, godot, luanti) lose crops beyond the in-frame test.",
    "T3_game_retrieval": "Frame -> other frames of the same game. seen: test_seen queries vs train gallery. unseen: leave-one-out inside test_unseen, own run excluded from gallery.",
    "T4_near_dup": "Perturbed frame -> its exact original among all test_unseen sample frames. Mild tier: 0.5x rescale, JPEG q40, brightness x1.25+10, 5% crop. Hard tier: 0.25x rescale, JPEG q10, colour cast, 15% crop per side, blur+noise, and a combined crop+0.5x+JPEG q25+brightness.",
    "T6_resleak": "Probe (letterbox 256): from T1-norm features only (no native size in the vector), predict a native-resolution bucket (max(w,h) in <=256 / 257-512 / >512). Size-only controls must be near chance. Image features above chance mean letterboxed pixels still leak native scale.",
    "T6_resleak_stretch": "Same probe as T6_resleak, but every frame is stretched to 256x256 (no letterbox bars), so aspect cannot leak through padding. This is the cleaner test of upscaling/downscaling traces.",
    "T5_style_cluster": "Unsupervised: k-means on test_unseen frame features with k = number of games; NMI/ARI/purity vs game (and vs source).",
}

CLF_METRICS = ("acc", "macro_f1", "bal_acc")
# test_unseen = released split (synth/roguelike: unseen genre/render/seed of seen games; others: whole games);
# test_unseen_games = strict subset whose game never appears in train/val/test_seen.
EVAL_REPORT = ("test_seen", "test_unseen", "test_unseen_games")


def _clf_scores(y, p, labels):
    return {"acc": M.accuracy(y, p), "macro_f1": M.macro_f1(y, p, labels=np.unique(y)), "bal_acc": M.balanced_accuracy(y, p), "n": int(len(y))}


def classification(feats, labels, seed, log, l2_grid=(1e-4, 1e-3, 1e-2), epochs=300, knn_k=(1, 10)):
    """feats[split] = dict(hist, phash, simple); labels[split] = array of str. Returns results + chosen hyperparams."""
    classes = np.array(sorted(set(labels["train"])))
    cidx = {c: i for i, c in enumerate(classes)}
    enc = lambda a: np.array([cidx.get(c, -1) for c in a], dtype=np.int64)
    ytr = enc(labels["train"])
    tr_h = B.hellinger_embed(feats["train"]["hist"])
    tr_p = B.hash_u64(feats["train"]["phash"])
    lr_x = lambda f: np.concatenate([B.hellinger_embed(f["hist"]), f["simple"]], 1)
    size_x = lambda f, key="size": np.concatenate([np.log(np.maximum(f[key], 1)), np.log(np.maximum(f[key][:, :1], 1) / np.maximum(f[key][:, 1:], 1))], 1)
    has_size = all("size" in f for f in feats.values())
    has_native = all("native_size" in f for f in feats.values())
    if has_size:  # shortcut probe: how much of the task is frame/crop size alone (size = what the model sees)
        sstd = B.Standardiser().fit(size_x(feats["train"]))
        tr_sz = sstd(size_x(feats["train"]))
        smodel = B.softmax_logreg(tr_sz, ytr, len(classes), 1e-3, epochs=epochs, seed=seed)
    if has_native:  # metadata control: original frame size, NOT visible to the normalised features
        nstd = B.Standardiser().fit(size_x(feats["train"], "native_size"))
        tr_nsz = nstd(size_x(feats["train"], "native_size"))
        nmodel = B.softmax_logreg(tr_nsz, ytr, len(classes), 1e-3, epochs=epochs, seed=seed)
    std = B.Standardiser().fit(lr_x(feats["train"]))
    xtr = std(lr_x(feats["train"]))
    # choose L2 on val
    best = None
    sel = {}
    if "val" in feats and len(labels["val"]):
        yv = enc(labels["val"])
        xv = std(lr_x(feats["val"]))
        for l2 in l2_grid:
            m = B.softmax_logreg(xtr, ytr, len(classes), l2, epochs=epochs, seed=seed)
            f1 = M.macro_f1(yv, B.logreg_predict(m, xv), labels=np.unique(yv))
            sel[str(l2)] = f1
            log(f"    logreg l2={l2:g} val macro_f1={f1:.4f}")
            if best is None or f1 > best[0]:
                best = (f1, l2, m)
        model, l2 = best[2], best[1]
    else:
        l2 = l2_grid[len(l2_grid) // 2]
        model = B.softmax_logreg(xtr, ytr, len(classes), l2, epochs=epochs, seed=seed)
    out = {}
    for split in EVAL_REPORT:
        if split not in feats or not len(labels[split]):
            continue
        y = enc(labels[split])
        n = len(y)
        res = {}
        res["random"] = _clf_scores(y, B.random_predict(n, len(classes), seed), classes)
        res["majority"] = _clf_scores(y, B.majority_predict(ytr, n), classes)
        qh = B.hellinger_embed(feats[split]["hist"])
        for k in knn_k:
            p = B.knn_predict(lambda a, b: qh[a:b] @ tr_h.T, ytr, n, k, n_classes=len(classes))
            res[f"hist_knn_k{k}"] = _clf_scores(y, p, classes)
        qp = B.hash_u64(feats[split]["phash"])
        p = B.knn_predict(lambda a, b: -B.hamming(qp[a:b], tr_p).astype(np.float32), ytr, n, 1, n_classes=len(classes))
        res["phash_knn_k1"] = _clf_scores(y, p, classes)
        if has_size:
            res["logreg_size_only"] = _clf_scores(y, B.logreg_predict(smodel, sstd(size_x(feats[split]))), classes)
            # kNN on size captures discrete native resolutions a linear model cannot
            q_sz = sstd(size_x(feats[split]))
            jit_amp = 1e-9 if float(np.abs(tr_sz).max()) == 0.0 else 0.0  # only a constant (normalised) size gets jitter, so raw T1 stays identical to v1
            jit = np.random.default_rng([seed, 7])  # seeded jitter: exact ties (constant size) break randomly, not by train order
            p = B.knn_predict(lambda a, b: -((q_sz[a:b, None, :] - tr_sz[None]) ** 2).sum(-1) + jit_amp * jit.random((b - a, len(tr_sz))), ytr, n, 10, n_classes=len(classes))
            res["size_knn_k10"] = _clf_scores(y, p, classes)
        if has_native:
            q_n = nstd(size_x(feats[split], "native_size"))
            res["native_size_logreg"] = _clf_scores(y, B.logreg_predict(nmodel, q_n), classes)
            p = B.knn_predict(lambda a, b: -((q_n[a:b, None, :] - tr_nsz[None]) ** 2).sum(-1), ytr, n, 10, n_classes=len(classes))
            res["native_size_knn_k10"] = _clf_scores(y, p, classes)
        res["logreg_hist+simple"] = _clf_scores(y, B.logreg_predict(model, std(lr_x(feats[split]))), classes)
        out[split] = res
        unk = int((y < 0).sum())
        if unk:
            log(f"    {split}: {unk} items with labels absent from train (always counted wrong)")
    return out, {"classes": classes.tolist(), "logreg_l2": l2, "logreg_val_macro_f1": sel}


def _retrieval_methods(q, g, seed):
    """Return {name: (score_fn, higher_better)} for query feats q and gallery feats g."""
    rng_seed = seed
    qh, gh = B.hellinger_embed(q["hist"]), B.hellinger_embed(g["hist"])
    qp, gp = B.hash_u64(q["phash"]), B.hash_u64(g["phash"])
    qd, gd = B.hash_u64(q["dhash"]), B.hash_u64(g["dhash"])
    std = B.Standardiser().fit(g["simple"])
    qs, gs = std(q["simple"]), std(g["simple"])
    qs /= np.linalg.norm(qs, axis=1, keepdims=True) + 1e-8; gs /= np.linalg.norm(gs, axis=1, keepdims=True) + 1e-8

    def rnd(a, b):
        return np.random.default_rng([rng_seed, a]).random((b - a, len(gh)), dtype=np.float32)
    return {
        "random": (rnd, True),
        "hist_hellinger": (lambda a, b: qh[a:b] @ gh.T, True),
        "phash_hamming": (lambda a, b: B.hamming(qp[a:b], gp), False),
        "dhash_hamming": (lambda a, b: B.hamming(qd[a:b], gd), False),
        "simple_cosine": (lambda a, b: qs[a:b] @ gs.T, True),
    }


def game_retrieval(feats, meta, seed, log):
    out = {}
    # seen: test_seen -> train
    key = lambda m: np.char.add(np.char.add(m["source"].astype(str), "/"), m["game"].astype(str))
    qg, gg = key(meta["test_seen"]), key(meta["train"])
    rel = lambda a, b: qg[a:b, None] == gg[None, :]
    res = {}
    for name, (fn, hb) in _retrieval_methods(feats["test_seen"], feats["train"], seed).items():
        res[name] = B.rank_eval(fn, len(qg), rel, higher_better=hb)
    out["test_seen"] = res
    # unseen: leave-one-out within the split, own run excluded from the gallery (no train gallery)
    for split in ("test_unseen", "test_unseen_games"):
        if split not in feats:
            continue
        ug = np.char.add(np.char.add(meta[split]["source"].astype(str), "/"), meta[split]["game"].astype(str))
        ur = np.char.add(np.char.add(ug, "/"), meta[split]["run"].astype(str))
        rel = lambda a, b, ug=ug: ug[a:b, None] == ug[None, :]
        valid = lambda a, b, ur=ur: ur[a:b, None] != ur[None, :]
        out[split] = {name: B.rank_eval(fn, len(ug), rel, valid_fn=valid, higher_better=hb)
                      for name, (fn, hb) in _retrieval_methods(feats[split], feats[split], seed).items()}
    return out


def near_dup(gallery, queries, q_orig_idx, q_kind, seed):
    """gallery: feats of originals; queries: feats of perturbed copies; q_orig_idx: gallery index of each query's original.
    Keys: each perturbation kind, `mild_all` / `hard_all` (pooled per tier; mild_all == v1's `all`)."""
    from .features import TIER_OF
    out = {}
    G = len(gallery["hist"])
    tier = np.array([TIER_OF[k] for k in q_kind])
    groups = [(k, q_kind == k) for k in dict.fromkeys(q_kind.tolist())]
    groups += [(f"{t}_all", tier == t) for t in ("mild", "hard") if (tier == t).any()]
    for kind, m in groups:
        q = {k: v[m] for k, v in queries.items()}
        oi = q_orig_idx[m]
        rel = lambda a, b, oi=oi: oi[a:b, None] == np.arange(G)[None, :]
        out[kind] = {name: B.rank_eval(fn, len(oi), rel, higher_better=hb)
                     for name, (fn, hb) in _retrieval_methods(q, gallery, seed).items()}
    return out


def style_cluster(feat, game, source, seed):
    game = np.char.add(np.char.add(np.asarray(source).astype(str), "/"), np.asarray(game).astype(str))
    k = len(np.unique(game))
    xs = {
        "kmeans_hist": B.hellinger_embed(feat["hist"]),
        "kmeans_simple": B.Standardiser().fit(feat["simple"])(feat["simple"]),
    }
    res = {"random": np.random.default_rng(seed).integers(0, k, len(game))}
    for name, x in xs.items():
        res[name] = B.kmeans(x, k, seed)
    out = {}
    for name, a in res.items():
        out[name] = {"NMI_game": M.nmi(game, a), "ARI_game": M.ari(game, a), "purity_game": M.purity(game, a),
                     "NMI_source": M.nmi(source, a), "k": int(k), "n": int(len(a))}
    return out


RESLEAK_EDGES = (256, 512)  # buckets: <=256, 257-512, >512 (native max side)


def resleak_bucket(w, h):
    m = max(int(w), int(h))
    if m <= RESLEAK_EDGES[0]:
        return "max<=256"
    if m <= RESLEAK_EDGES[1]:
        return "max257-512"
    return "max>512"


def resolution_leak(feats, native_size, seed, log, l2_grid=(1e-4, 1e-3, 1e-2), epochs=300):
    """feats[split] has hist/simple (from normalised frames); native_size[split] is (n,2) original w,h.
    Same protocol as T1 (train, val L2, report seen / unseen / unseen-games)."""
    labels = {s: np.array([resleak_bucket(w, h) for w, h in native_size[s]]) for s in feats}
    counts = {s: {k: int(v) for k, v in zip(*np.unique(labels[s], return_counts=True))} for s in labels}
    log(f"    resleak bucket counts: {counts}")
    if len(set(labels["train"])) < 2:
        log("    resleak skipped: train has fewer than two native-size buckets")
        return {}, {"skipped": True, "bucket_counts": counts, "buckets": sorted(set(labels["train"]))}
    r, hp = classification(feats, labels, seed, log, l2_grid=l2_grid, epochs=epochs)
    hp["buckets"] = sorted(set(labels["train"]))
    hp["bucket_counts"] = counts
    # image methods should be compared to size-only (must be ~chance: the model-visible size is constant)
    return r, hp
