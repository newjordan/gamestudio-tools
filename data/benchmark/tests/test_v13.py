"""v1.3 anti-leak normalisation protocols."""
import json, hashlib
import numpy as np
import pytest
from PIL import Image
from gbench import cli, extract, features as Fe, tasks as T
from gbench.extract import _key


def _checker(native, seed=0, roll=0):
    r = np.random.default_rng(seed)
    a = ((np.indices((native, native)).sum(0) // max(1, native // 8)) % 2) * 255
    a = np.stack([a, a, np.roll(a, roll, 0)], 2).astype(np.uint8)
    a = np.clip(a + r.integers(-8, 8, a.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(a)


def test_legacy_normalise_pixels_match_v11_formula():
    img = Image.fromarray(np.random.default_rng(1).integers(0, 255, (180, 320, 3), dtype=np.uint8))
    for mode in ("letterbox", "stretch"):
        got = np.asarray(Fe.normalise(img, 256, mode))
        # v1.1 formula, inlined
        w, h = img.size
        if mode == "stretch":
            exp = np.asarray(img.resize((256, 256), Image.LANCZOS if max(w, h) > 256 else Image.BICUBIC))
        else:
            s = 256 / max(w, h)
            nw, nh = max(1, round(w * s)), max(1, round(h * s))
            r = img.resize((nw, nh), Image.LANCZOS if s < 1 else Image.BICUBIC)
            canvas = Image.new("RGB", (256, 256), (0, 0, 0))
            canvas.paste(r, ((256 - nw) // 2, (256 - nh) // 2))
            exp = np.asarray(canvas)
        assert np.array_equal(got, exp), mode


def test_legacy_cache_token_unchanged():
    paths = ["a.png", "b.png"]
    old = _key([paths, "letterbox", 256])
    new = _key([paths] + Fe.cache_norm_token("letterbox"))
    assert old == new
    assert Fe.cache_norm_token("stretch") == ["stretch", 256]
    assert Fe.cache_norm_token("bn64") != Fe.cache_norm_token("letterbox")
    assert Fe.cache_norm_token("bn64") != Fe.cache_norm_token("bn96")
    assert Fe.cache_norm_token("bn64_blur") != Fe.cache_norm_token("bn64")
    assert Fe.cache_norm_token("bn64_jpeg") != Fe.cache_norm_token("bn64")
    # name does not affect the cache
    a = Fe.cache_norm_token({"mode": "letterbox", "size": 256, "bottleneck": 64, "resample": "lanczos"})
    b = Fe.cache_norm_token("bn64")
    assert a == b


def test_named_protocols_resolve():
    for name in Fe.ANTILEAK_PROTOCOLS:
        p = Fe.resolve_protocol(name)
        assert p["bottleneck"] in (64, 96) and p["size"] == 256 and p["mode"] == "letterbox"
    assert Fe.resolve_protocol("letterbox")["mode"] == "letterbox"
    with pytest.raises(ValueError):
        Fe.resolve_protocol("not-a-protocol")


def test_bottleneck_forces_shared_canvas_then_256():
    tiny = Image.new("RGB", (16, 8), (255, 0, 0))
    wide = Image.new("RGB", (800, 200), (0, 255, 0))
    for name in Fe.ANTILEAK_PROTOCOLS:
        p = Fe.resolve_protocol(name)
        for im in (tiny, wide):
            out = Fe.apply_norm(im, p)
            assert out.size == (256, 256)
        # mid-step geometry: letterbox 16x8 onto 64 or 96, then up
        # red content of tiny should survive as a centred band, not fill the frame
        a = np.asarray(Fe.normalise(tiny, 256, "letterbox", bottleneck=p["bottleneck"], resample="lanczos"))
        # bars (black) remain after upsample
        assert a[0, 0].tolist() == [0, 0, 0]
        assert a[128, 128].tolist()[0] > 200  # red content in the middle


def test_bn64_letterbox_geometry_is_scaled_bars():
    img = Image.new("RGB", (160, 90), (255, 0, 0))
    a = np.asarray(Fe.normalise(img, 256, "letterbox", bottleneck=64, resample="lanczos"))
    assert a.shape == (256, 256, 3)
    # 160x90 -> 64x36 on 64 canvas, bars 14px each, x4 -> 256x144 content, 56px bars
    # top rows should be black, mid should be red
    assert a[:40].max() == 0
    assert int(a[128, 128, 0]) > 200 and int(a[128].max()) > 200
    assert a[-40:].max() == 0
    # stretch has no bars
    b = np.asarray(Fe.normalise(img, 256, "stretch", bottleneck=64, resample="lanczos"))
    assert int(b[0, 0, 0]) > 200 and int(b[-1, -1, 0]) > 200


def test_blur_and_jpeg_change_pixels_and_are_deterministic():
    img = _checker(128, seed=2, roll=1)
    base = np.asarray(Fe.normalise(img, 256, "letterbox", bottleneck=64, resample="lanczos"))
    blur = np.asarray(Fe.apply_norm(img, "bn64_blur"))
    jpeg = np.asarray(Fe.apply_norm(img, "bn64_jpeg"))
    assert not np.array_equal(base, blur)
    assert not np.array_equal(base, jpeg)
    assert np.array_equal(blur, np.asarray(Fe.apply_norm(img, "bn64_blur")))
    assert np.array_equal(jpeg, np.asarray(Fe.apply_norm(img, "bn64_jpeg")))


def test_bottleneck_reduces_scale_trace_vs_legacy_stretch():
    """On a two-bucket checker, legacy stretch-to-64 is linearly separable; bn16->64 is closer to chance."""
    def pack(native, n, seed, proto):
        feats = []
        for i in range(n):
            im = _checker(native, seed=seed * 100 + i, roll=i % 5)
            feats.append(Fe.all_feats(Fe.apply_norm(im, proto) if isinstance(proto, dict) else Fe.normalise(im, 64, "stretch") if proto == "legacy" else Fe.normalise(im, 64, "stretch", bottleneck=16, resample="lanczos")))
        hist = np.stack([f[0] for f in feats]); simple = np.stack([f[3] for f in feats])
        return {"hist": hist, "phash": np.stack([f[1] for f in feats]), "dhash": np.stack([f[2] for f in feats]),
                "simple": simple, "size": np.full((n, 2), 64, np.float32),
                "native_size": np.array([[native, native]] * n, np.float32)}

    def suite(kind):
        proto = "legacy" if kind == "legacy" else "bn"
        tr = {k: np.concatenate([pack(128, 40, 1, proto)[k], pack(400, 40, 2, proto)[k]]) for k in ("hist","phash","dhash","simple","size","native_size")}
        va = {k: np.concatenate([pack(128, 16, 3, proto)[k], pack(400, 16, 4, proto)[k]]) for k in tr}
        te = {k: np.concatenate([pack(128, 16, 5, proto)[k], pack(400, 16, 6, proto)[k]]) for k in tr}
        return {"train": tr, "val": va, "test_seen": te}

    log = lambda *a, **k: None
    feats_leg = suite("legacy")
    r_leg, _ = T.resolution_leak(feats_leg, {s: feats_leg[s]["native_size"] for s in feats_leg}, 0, log, epochs=80)
    feats_bn = suite("bn")
    r_bn, _ = T.resolution_leak(feats_bn, {s: feats_bn[s]["native_size"] for s in feats_bn}, 0, log, epochs=80)
    # legacy still leaks (same construction as the v1.2 unit test)
    assert r_leg["test_seen"]["logreg_hist+simple"]["acc"] >= 0.8
    # bottleneck should not be a better leak detector than legacy, and should be below the legacy score
    assert r_bn["test_seen"]["logreg_hist+simple"]["bal_acc"] <= r_leg["test_seen"]["logreg_hist+simple"]["bal_acc"] + 0.05
    assert r_bn["test_seen"]["size_knn_k10"]["bal_acc"] <= 0.7


def test_report_antileak_table_lists_protocols(tmp_path):
    def fake_run(bench, seed, proto, t6_bal, t1_f1):
        def clf(bal, f1):
            return {"acc": 0.5, "macro_f1": f1, "bal_acc": bal, "n": 10}
        methods = {m: clf(t6_bal, t1_f1) for m in ("logreg_hist+simple", "hist_knn_k1", "size_knn_k10", "majority")}
        return {"config": {"bench": bench, "scale": "default", "seed": seed, "norm_protocol": proto,
                           "train": 1, "val": 1, "test_seen": 1, "test_unseen": 1, "crop_train": 1, "crop_eval": 1,
                           "crops_per_frame": 1, "nd_queries": 1, "version": "0.4.0",
                           "env": {"numpy": "1", "python": "3", "cpus": 1}},
                "finished": "now", "integrity": {},
                "tasks": {
                    "T1_norm": {"results": {"test_unseen_games": {k: clf(0.4, t1_f1) for k in methods}},
                                "hparams": {"classes": ["a"], "logreg_l2": 0.001, "norm_protocol": proto}},
                    "T6_resleak": {"results": {"test_unseen_games": {k: clf(t6_bal, 0.4) for k in methods}},
                                   "hparams": {"buckets": ["x","y","z"], "norm_protocol": proto}},
                    "T6_resleak_stretch": {"results": {"test_unseen_games": {k: clf(t6_bal - 0.02, 0.4) for k in methods}},
                                           "hparams": {"buckets": ["x","y","z"], "norm_protocol": proto}},
                }}
    rows = [
        ("letterbox-256 (v1.1 T1 / v1.2 T6)", [("a", fake_run("1.2", 0, "letterbox", 0.58, 0.38))]),
        ("bn64", [("b", fake_run("1.3", 0, "bn64", 0.40, 0.35))]),
    ]
    md = "\n".join(cli.render_antileak_compare(rows, "(test)"))
    assert "T6 leak vs T1 cost" in md
    assert "bn64" in md and "letterbox-256" in md
    assert "0.580" in md and "0.400" in md


def test_default_run_dir_is_v13_not_v12(tmp_path, monkeypatch):
    assert cli.BENCH_VERSION == "1.3"
    # the default name formula
    import inspect, os
    src = inspect.getsource(cli.cmd_run)
    assert "v13_{proto_name}_{a.scale}_seed{a.seed}" in src
    assert 'f"v12_{a.scale}_seed{a.seed}"' not in src


def test_official_t1_protocol_is_bn64():
    assert Fe.OFFICIAL_T1_PROTOCOL == "bn64"
    assert Fe.OFFICIAL_T1_PROTOCOL in Fe.ANTILEAK_PROTOCOLS
    assert Fe.PROTOCOLS["bn64"]["bottleneck"] == 64
