import itertools, json, os
import numpy as np
from PIL import Image
from gbench import baselines as B, data, features as Fe, metrics as M


def test_classification_metrics():
    y = np.array([0, 0, 1, 1, 2, 2]); p = np.array([0, 1, 1, 1, 2, 0])
    assert M.accuracy(y, p) == 4 / 6
    # per-class F1: c0 tp1 fp1 fn1 ->0.5 ; c1 tp2 fp1 fn0 -> .8 ; c2 tp1 fp0 fn1 -> 2/3
    assert abs(M.macro_f1(y, p) - np.mean([0.5, 0.8, 2 / 3])) < 1e-9
    assert abs(M.balanced_accuracy(y, p) - np.mean([0.5, 1, 0.5])) < 1e-9


def test_cluster_metrics():
    t = np.array([0, 0, 1, 1, 2, 2])
    assert M.nmi(t, np.array([5, 5, 7, 7, 9, 9])) == 1.0
    assert abs(M.ari(t, np.array([1, 1, 0, 0, 2, 2])) - 1.0) < 1e-12
    assert M.purity(t, np.zeros(6)) == 2 / 6
    # ARI of a known case (hand computed): sklearn gives 0.24242424...
    assert abs(M.ari([0, 0, 0, 1, 1, 1], [0, 0, 1, 1, 2, 2]) - 0.2424242424) < 1e-6


def test_rank_eval_toy():
    # 2 queries, gallery of 4; scores make ranks explicit
    S = np.array([[0.9, 0.1, 0.8, 0.0], [0.1, 0.2, 0.3, 0.4]])
    R = np.array([[False, False, True, True], [False, False, False, False]])
    r = B.rank_eval(lambda a, b: S[a:b], 2, lambda a, b: R[a:b], ks=(1, 2, 3))
    # q0 ranking: g0 g2 g1 g3 -> rel 0 1 0 1 -> AP = (1/2 + 2/4)/2 = 0.5; q1 skipped (no positives)
    assert r["n_queries"] == 1 and r["R@1"] == 0 and r["R@2"] == 1 and abs(r["mAP"] - 0.5) < 1e-6
    # excluding g2 via valid mask
    V = np.array([[True, True, False, True], [True] * 4])
    r = B.rank_eval(lambda a, b: S[a:b], 2, lambda a, b: R[a:b], valid_fn=lambda a, b: V[a:b], ks=(1,))
    assert abs(r["mAP"] - 1 / 3) < 1e-6


def test_hamming_matches_python():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 256, (5, 8), dtype=np.uint8); b = rng.integers(0, 256, (7, 8), dtype=np.uint8)
    d = B.hamming(B.hash_u64(a), B.hash_u64(b))
    for i, j in itertools.product(range(5), range(7)):
        assert d[i, j] == sum(bin(x ^ y).count("1") for x, y in zip(a[i], b[j]))


def test_phash_robust_and_discriminative():
    rng = np.random.default_rng(2)
    a = (rng.random((96, 128, 3)) * 255).astype(np.uint8)
    a[20:60, 30:90] = 255
    img = Image.fromarray(a)
    other = Image.fromarray((rng.random((96, 128, 3)) * 255).astype(np.uint8))
    h = B.hash_u64(Fe.phash(img)[None])
    d_self = B.hamming(h, B.hash_u64(Fe.phash(Fe.augment(img, "rescale"))[None]))[0, 0]
    d_other = B.hamming(h, B.hash_u64(Fe.phash(other)[None]))[0, 0]
    assert d_self < 10 < d_other


def test_colour_hist_normalised():
    h = Fe.colour_hist(Image.new("RGB", (10, 10), (255, 0, 0)))
    assert h.shape == (512,) and abs(h.sum() - 1) < 1e-6 and h.argmax() == 7 * 64
    assert Fe.simple_feats(Image.new("RGB", (20, 10))).shape == (Fe.SIMPLE_DIM,)
    # RGBA / palette images do not crash
    Fe.all_feats(Image.new("RGBA", (12, 12), (1, 2, 3, 0))); Fe.all_feats(Image.new("P", (12, 12)))


def test_logreg_separable():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(-3, 1, (100, 4)), rng.normal(3, 1, (100, 4))]).astype(np.float32)
    y = np.array([0] * 100 + [1] * 100)
    m = B.softmax_logreg(x, y, 2, 1e-3, epochs=100)
    assert M.accuracy(y, B.logreg_predict(m, x)) > 0.98


def test_knn_and_baselines():
    tr = np.eye(3, dtype=np.float32); ytr = np.array([0, 1, 2])
    q = np.array([[0.9, 0.1, 0], [0, 0, 1]], np.float32)
    assert B.knn_predict(lambda a, b: q[a:b] @ tr.T, ytr, 2, 1).tolist() == [0, 2]
    assert B.knn_predict(lambda a, b: q[a:b] @ tr.T, ytr, 2, 3, n_classes=3).tolist() == [0, 2]  # tie -> nearest
    assert (B.majority_predict(np.array([1, 1, 2]), 4) == 1).all()
    assert (B.random_predict(10, 3, 5) == B.random_predict(10, 3, 5)).all()


def test_kmeans_blobs():
    rng = np.random.default_rng(0)
    c = np.array([[0, 0], [10, 10], [-10, 10]])
    x = np.concatenate([rng.normal(ci, 0.5, (30, 2)) for ci in c])
    t = np.repeat([0, 1, 2], 30)
    assert M.ari(t, B.kmeans(x, 3, seed=0)) > 0.99


def test_sample_per_game_deterministic_and_capped():
    rows = [{"source": "s", "game": g, "run": f"r{r}", "path": f"{g}/{r}/{t}"} for g in "ab" for r in range(3) for t in range(5)]
    a = data.sample_per_game(rows, 3, seed=1); b = data.sample_per_game(list(reversed(rows)), 3, seed=1)
    assert [r["path"] for r in a] == [r["path"] for r in b]
    assert len(a) == 6
    for g in "ab":  # runs spread: 3 picks from 3 distinct runs
        assert len({r["run"] for r in a if r["game"] == g}) == 3
    assert data.sample_per_game(rows, 99, seed=1).__len__() == 30


def test_integrity_detects_leaks():
    base = {"source": "x", "t": 0}
    ok = {"train": [dict(base, game="a", run="1", md5="m1")], "test_unseen": [dict(base, game="b", run="2", md5="m2")]}
    assert not any(data.check_integrity(ok).values())
    bad = {"train": [dict(base, game="a", run="1", md5="m1")], "test_unseen": [dict(base, game="a", run="1", md5="m1")]}
    r = data.check_integrity(bad)
    assert r["unseen_games_also_seen_non_synth_roguelike"] == 1 and r["runs_shared_train_test_unseen"] == 1 and r["md5_shared_train_test_unseen"] == 1
    syn = {"train": [dict(base, source="synth", game="a", run="1", md5="m1")], "test_unseen": [dict(base, source="synth", game="a", run="9", md5="m9")]}
    assert not any(data.check_integrity(syn).values())  # unseen-kind sources are allowed to share game names


def test_record_reader_plain_and_gz(fake):
    rr = data.RecordReader(fake["root"])
    for r in fake["splits"]["train"] + fake["splits"]["test_unseen"]:
        rec = rr.read(r["rec"], r["off"])
        assert rec["image"] == r["path"]


def test_entity_sem_mapping():
    cmap = {"s": {"hero": {"sem": "character"}}}
    assert data.entity_sem({"class": "hero"}, "s", cmap) == "character"
    assert data.entity_sem({"class": "zzz", "sem": "item"}, "s", cmap) == "item"
    assert data.entity_sem({"class": "zzz"}, "s", cmap) == "unknown"
