import json, os
import numpy as np
import pytest
from PIL import Image
from gbench import data, features as Fe, tasks as T, classmap
from gbench.cli import HERE

V12 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "class_map_v1.2.json")
V1 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "class_map_v1.json")


@pytest.fixture(scope="module")
def maps():
    v1 = json.load(open(V1))
    v12 = json.load(open(V12))
    return v1, v12


def test_v12_map_is_versioned_copy_not_a_rewrite(maps):
    v1, v12 = maps
    assert v12["vocab"] == v1["vocab"] == data.load_class_map(V1)[0]
    assert set(v12["map"]) == set(v1["map"])
    # every class still present; only listed changes differ in sem
    changed = {(c["source"], c["raw"]) for c in v12["changes"]}
    n_diff = 0
    for src, classes in v1["map"].items():
        assert set(classes) == set(v12["map"][src])
        for raw, e in classes.items():
            n = v12["map"][src][raw]
            assert n["n"] == e["n"]
            if (src, raw) in changed:
                n_diff += 1
                assert n["sem"] != e["sem"]
            else:
                assert n["sem"] == e["sem"], (src, raw, e["sem"], n["sem"])
    assert n_diff == len(v12["changes"]) == 20


def test_v12_card_character_tree_remaps(maps):
    v1, v12 = maps
    hearts = [c for c in v12["changes"] if c["raw"].startswith("card_hearts")]
    assert len(hearts) == 6 and all(c["old"] == "item" and c["new"] == "card" for c in hearts)
    assert sum(c["n"] for c in hearts) == 91106
    assert v12["map"]["synth"]["card_clubs"]["sem"] == "card"  # unchanged
    chars = [c for c in v12["changes"] if c["raw"].startswith("character_")]
    assert len(chars) == 12 and all(c["old"] == "prop" and c["new"] == "character" for c in chars)
    assert sum(c["n"] for c in chars) == 81122
    assert v12["map"]["synth"]["character"]["sem"] == "character"
    trees = [c for c in v12["changes"] if "tree" in c["raw"]]
    assert {c["raw"] for c in trees} == {"tree_large", "tree_small"}
    assert all(c["old"] == "prop" and c["new"] == "decor" for c in trees)
    assert sum(c["n"] for c in trees) == 6997 + 6893
    # hand-labelled synth tiles and non-plant names stay put
    for src, raw, sem in (("synth", "tree", "prop"), ("synth", "dead_tree", "prop"), ("synth", "trees", "decor"),
                          ("godot", "tree_bark", "ui"), ("luanti", "mobs_monster_tree_monster", "enemy"),
                          ("web", "tree", "decor"), ("roguelike", "tree", "decor")):
        assert v12["map"][src][raw]["sem"] == sem == v1["map"][src][raw]["sem"]
    assert "agent" not in v12["vocab"]  # no invented class; character_* go to character


def test_v12_changes_counts_match_parent_map(maps):
    v1, v12 = maps
    for c in v12["changes"]:
        assert v1["map"][c["source"]][c["raw"]]["n"] == c["n"]
        assert v1["map"][c["source"]][c["raw"]]["sem"] == c["old"]
        assert v12["map"][c["source"]][c["raw"]]["sem"] == c["new"]
        assert c["evidence"]


def test_entity_sem_prefers_game_scoped_key():
    cmap = {"web": {"chars": {"sem": "unknown"}, "astrohop/chars": {"sem": "character"}, "tree": {"sem": "decor"}}}
    assert data.entity_sem({"class": "chars"}, "web", cmap, game="astrohop") == "character"
    assert data.entity_sem({"class": "chars"}, "web", cmap, game="other") == "unknown"
    assert data.entity_sem({"class": "chars"}, "web", cmap) == "unknown"  # no game: bare key (v1.1 behaviour)
    assert data.entity_sem({"class": "tree"}, "web", cmap, game="x") == "decor"
    assert data.entity_sem({"class": "zzz", "sem": "item"}, "web", cmap, game="x") == "item"
    assert data.entity_sem({"class": "zzz"}, "web", cmap, game="x") == "unknown"


def test_resleak_bucket_edges():
    assert T.resleak_bucket(256, 64) == "max<=256"
    assert T.resleak_bucket(257, 64) == "max257-512"
    assert T.resleak_bucket(512, 512) == "max257-512"
    assert T.resleak_bucket(513, 1) == "max>512"
    assert T.resleak_bucket(640, 360) == "max>512"


def test_resolution_leak_detects_upscale_traces_on_stretch():
    """Two native sizes, stretched to 64px: a sharp 64x64 pattern vs a 16x16 pattern upscaled to 64.
    A classifier on the normalised simple/hist features should beat chance; size-only cannot."""
    rng = np.random.default_rng(0)
    def mk(native, n, seed):
        r = np.random.default_rng(seed)
        imgs = []
        for i in range(n):
            # high-contrast checker at native resolution, then we'll stretch
            a = ((np.indices((native, native)).sum(0) // max(1, native // 8)) % 2) * 255
            a = np.stack([a, a, np.roll(a, i % 3, 0)], 2).astype(np.uint8)
            a = np.clip(a + r.integers(-8, 8, a.shape), 0, 255).astype(np.uint8)
            imgs.append(Image.fromarray(a))
        feats = [Fe.all_feats(Fe.normalise(im, 64, "stretch")) for im in imgs]
        hist = np.stack([f[0] for f in feats]); simple = np.stack([f[3] for f in feats])
        return {"hist": hist, "phash": np.stack([f[1] for f in feats]), "dhash": np.stack([f[2] for f in feats]),
                "simple": simple, "size": np.full((n, 2), 64, np.float32), "native_size": np.array([[native, native]] * n, np.float32)}
    tr = {k: np.concatenate([mk(128, 40, 1)[k], mk(400, 40, 2)[k]]) for k in ("hist","phash","dhash","simple","size","native_size")}
    va = {k: np.concatenate([mk(128, 16, 3)[k], mk(400, 16, 4)[k]]) for k in tr}
    te = {k: np.concatenate([mk(128, 16, 5)[k], mk(400, 16, 6)[k]]) for k in tr}
    feats = {"train": tr, "val": va, "test_seen": te}
    log = lambda *a, **k: None
    r, hp = T.resolution_leak(feats, {s: feats[s]["native_size"] for s in feats}, seed=0, log=log, epochs=80)
    assert r["test_seen"]["size_knn_k10"]["bal_acc"] <= 0.7
    # image model should separate the two scale-generated textures
    assert r["test_seen"]["logreg_hist+simple"]["acc"] >= 0.8
    assert r["test_seen"]["logreg_hist+simple"]["acc"] > r["test_seen"]["majority"]["acc"]


def test_resolution_leak_skips_single_bucket():
    hist = np.zeros((4, 512), np.float32); hist[:,0]=1
    f = {"hist": hist, "phash": np.zeros((4,8), np.uint8), "dhash": np.zeros((4,8), np.uint8),
         "simple": np.zeros((4, Fe.SIMPLE_DIM), np.float32), "size": np.full((4,2), 256, np.float32)}
    ns = {"train": np.array([[64,64]]*4), "val": np.array([[64,64]]*4), "test_seen": np.array([[64,64]]*4)}
    r, hp = T.resolution_leak({"train": f, "val": f, "test_seen": f}, ns, 0, lambda *a: None)
    assert hp["skipped"] is True and r == {}


def test_classmap_audit_includes_v12_changes(maps, tmp_path):
    from gbench import cli
    out = tmp_path / "a.md"
    assert cli.main(["--class-map", V12, "classmap", "--out", str(out)]) == 0
    t = out.read_text()
    assert "card_hearts" in t and "character_black_green" in t and "tree_large" in t
    assert "91,106" in t or "19,705" in t
    assert "v1.2 mapping changes" in t
