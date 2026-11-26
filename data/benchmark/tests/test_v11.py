import json, shutil
import numpy as np
import pytest
from PIL import Image
from gbench import classmap, cli, features as Fe, occlusion as O


# ---------- normalisation
def test_letterbox_geometry():
    img = Image.new("RGB", (160, 90), (255, 0, 0))
    n = Fe.normalise(img, 256, "letterbox")
    a = np.asarray(n)
    assert n.size == (256, 256)
    # 160x90 -> 256x144, centred: bars of 56 rows top and bottom are black, middle is red
    assert (a[:56] == 0).all() and (a[-56:] == 0).all()
    assert (a[56:200, :, 0] > 250).all() and (a[56:200, :, 1:] < 5).all()


def test_stretch_has_no_bars_and_modes_validated():
    n = np.asarray(Fe.normalise(Image.new("RGB", (160, 90), (0, 255, 0)), 256, "stretch"))
    assert n.shape == (256, 256, 3) and (n[:, :, 1] > 250).all()
    with pytest.raises(ValueError):
        Fe.normalise(Image.new("RGB", (8, 8)), 256, "crop")


def test_normalise_handles_rgba_palette_and_tiny():
    for im in (Image.new("RGBA", (10, 40), (1, 2, 3, 0)), Image.new("P", (3, 3)), Image.new("RGB", (1, 1))):
        for m in Fe.NORM_MODES:
            assert Fe.normalise(im, 64, m).size == (64, 64)


def test_normalised_features_ignore_native_resolution():
    a = np.zeros((90, 160, 3), np.uint8)
    a[:45, :80] = (255, 0, 0); a[:45, 80:] = (0, 255, 0); a[45:, :80] = (0, 0, 255); a[45:, 80:] = (250, 250, 20)
    big = Image.fromarray(a)
    small = big.resize((80, 45), Image.LANCZOS)
    hb, _, _, sb = Fe.all_feats(Fe.normalise(big, 256, "stretch"))
    hs, _, _, ss = Fe.all_feats(Fe.normalise(small, 256, "stretch"))
    assert sb[-2] == ss[-2]  # aspect feature identical (both 256x256 after normalising); raw would differ by size only
    assert np.abs(hb - hs).sum() < 0.1
    # raw features do carry the aspect/size signal
    assert Fe.simple_feats(Image.new("RGB", (160, 90)))[-2] != Fe.simple_feats(Image.new("RGB", (90, 160)))[-2]


# ---------- occlusion filter
def test_in_frame_fraction():
    assert O.in_frame_fraction([0, 0, 10, 10], 100, 100) == 1.0
    assert O.in_frame_fraction([-5, 0, 10, 10], 100, 100) == 0.5
    assert O.in_frame_fraction([200, 200, 10, 10], 100, 100) == 0.0
    assert O.in_frame_fraction([0, 0, 0, 10], 100, 100) == 0.0


@pytest.mark.parametrize("ent,expect", [
    ({"vanished": True}, "vanished"),
    ({"truncated": True}, "truncated"),
    ({"visible_frac": 0.3, "visibility": 1.0}, "low_visible_frac"),   # measured visible_frac wins over the estimate
    ({"visible_frac": None, "visibility": 0.2}, "low_visible_frac"),  # falls back to visibility when visible_frac is null
    ({"visible_frac": None, "visibility": 0.9}, None),
    ({"occluded": True}, "occluded_flag"),
    ({"occluded": False}, None),
    ({"occluded": 0.8}, "occluded_frac"),
    ({"occluded": 0.2}, None),
    ({"vis": 0.01}, None),     # `vis` semantics are ambiguous across engines and deliberately ignored
    ({}, None),
])
def test_occlusion_reason(ent, expect):
    assert O.occlusion_reason(ent, [10, 10, 20, 20], 100, 100) == expect


def test_occlusion_off_frame_and_thresholds():
    assert O.occlusion_reason({}, [90, 0, 20, 20], 100, 100) == "off_frame"          # half outside
    assert O.occlusion_reason({}, [90, 0, 20, 20], 100, 100, min_in_frame=0.4) is None
    assert O.occlusion_reason({"visible_frac": 0.6}, [0, 0, 5, 5], 100, 100) is None
    assert O.occlusion_reason({"visible_frac": 0.6}, [0, 0, 5, 5], 100, 100, min_visible=0.7) == "low_visible_frac"
    assert O.occlusion_info({"visibility": 1}) and not O.occlusion_info({"class": "x", "vis": 0.5})


# ---------- hard perturbations
def _img():
    rng = np.random.default_rng(3)
    a = (rng.random((96, 128, 3)) * 255).astype(np.uint8)
    a[20:60, 30:90] = 200
    return Image.fromarray(a)


def test_hard_tier_defined_and_disjoint():
    assert set(Fe.AUG_KINDS) == {"rescale", "jpeg", "bright", "crop"}
    assert len(Fe.HARD_KINDS) == 6 and not set(Fe.AUG_KINDS) & set(Fe.HARD_KINDS)
    assert all(Fe.TIER_OF[k] == "hard" for k in Fe.HARD_KINDS) and all(Fe.TIER_OF[k] == "mild" for k in Fe.AUG_KINDS)


def test_hard_augment_deterministic_and_harsher():
    img = _img()
    for k in Fe.HARD_KINDS:
        a, b = Fe.augment(img, k, seed=5), Fe.augment(img, k, seed=5)
        assert np.array_equal(np.asarray(a), np.asarray(b)), k
    assert not np.array_equal(np.asarray(Fe.augment(img, "h_noise", seed=1)), np.asarray(Fe.augment(img, "h_noise", seed=2)))
    assert Fe.augment(img, "h_rescale").size[0] < Fe.augment(img, "rescale").size[0]
    assert Fe.augment(img, "h_crop").size[0] < Fe.augment(img, "crop").size[0]
    assert Fe.augment(img, "h_combo").size[0] < img.size[0] // 2
    # mild kinds are byte-identical to v1 behaviour (no seed dependence)
    for k in Fe.AUG_KINDS:
        assert np.array_equal(np.asarray(Fe.augment(img, k, seed=1)), np.asarray(Fe.augment(img, k, seed=99)))
    # JPEG q10 is lossier than q40
    base = np.asarray(img).astype(float)
    e = lambda k: np.abs(np.asarray(Fe.augment(img, k)).astype(float) - base).mean()
    assert e("h_jpeg") > e("jpeg")


# ---------- class-map audit
CMAP = {
    "synth": {"card_hearts": {"sem": "item", "n": 500}, "card_clubs": {"sem": "card", "n": 800}, "card_spades": {"sem": "card", "n": 700},
              "tree": {"sem": "prop", "n": 300}},
    "web": {"tree": {"sem": "decor", "n": 400}, "blob": {"sem": "unknown", "n": 100}},
}


def test_classmap_audit_finds_mixed_family_and_cross_source():
    a = classmap.audit(CMAP, min_boxes=100)
    m = [x for x in a["mixed_families"] if x["source"] == "synth" and x["family"] == "card"]
    assert m and m[0]["sems"] == {"item": 500, "card": 1500} and m[0]["boxes"] == 2000
    assert a["cross_source"][0]["raw"] == "tree"
    assert abs(a["per_source"]["web"]["unknown_share"] - 0.2) < 1e-9
    txt = classmap.render(a)
    assert "card_hearts" in txt and "`tree`" in txt and txt.count("\n|---") >= 3
    assert classmap.family("Card_Hearts_Q2") == "card" and classmap.family("2d_nav") == "2d"


# ---------- v1 compat / reporting
def test_table_maps_v1_all_key_and_compare_versions():
    R1 = {"config": {"seed": 0}, "tasks": {"T4_near_dup": {"results": {"all": {"phash_hamming": {"R@1": 0.5, "mAP": 0.6}}}}}}
    R2 = {"config": {"seed": 0}, "tasks": {"T4_near_dup": {"results": {"mild_all": {"phash_hamming": {"R@1": 0.5, "mAP": 0.6}}, "hard_all": {"phash_hamming": {"R@1": 0.1, "mAP": 0.2}}}}}}
    assert ("T4_near_dup", "mild_all", "phash_hamming", "R@1") in cli._table(R1)
    txt = "\n".join(cli.compare_versions([("a", R1)], [("b", R2)]))
    assert "2 (seed" in txt and "2 are identical" in txt and "0 differ" in txt
    R2["tasks"]["T4_near_dup"]["results"]["mild_all"]["phash_hamming"]["R@1"] = 0.4
    assert "1 differ" in "\n".join(cli.compare_versions([("a", R1)], [("b", R2)]))


# ---------- end to end on the toy dataset
def _args(fake):
    return ["--clean", fake["clean"], "--data-root", fake["root"], "--class-map", fake["class_map"]]


def _run(fake, tmp_path, name, extra=(), cache="feat"):
    out = tmp_path / name
    rc = cli.main(_args(fake) + ["run", "--scale", "smoke", "--workers", "2", "--out", str(out), "--cache", str(tmp_path / cache)] + list(extra))
    assert rc == 0
    return json.load(open(out / "results.json")), out


@pytest.fixture(scope="module")
def e2e(fake, tmp_path_factory):
    return _run(fake, tmp_path_factory.mktemp("e2e"), "full")


def test_t1_norm_removes_size_shortcut(e2e):
    R, _ = e2e
    raw, norm, st = (R["tasks"][t]["results"] for t in ("T1_source_id", "T1_norm", "T1_norm_stretch"))
    K = len(R["tasks"]["T1_norm"]["hparams"]["classes"])
    # toy data: sources differ only by frame size AND texture. Raw size control exploits the size.
    assert raw["test_seen"]["size_knn_k10"]["bal_acc"] > 0.9
    for t in ("T1_norm", "T1_norm_stretch"):
        chk = R["tasks"][t]["shortcut_check"]
        assert chk["size_control_near_chance"] is True
        for tt in (R["tasks"][t]["results"]):
            sc = R["tasks"][t]["results"][tt]
            assert sc["size_knn_k10"]["bal_acc"] <= 2 / K and sc["logreg_size_only"]["bal_acc"] <= 2 / K
            # the hidden metadata control still shows the shortcut exists in the data
            assert sc["native_size_knn_k10"]["bal_acc"] > 0.9
    assert "native_size_knn_k10" not in raw["test_seen"]


def test_t2_occ_filter_drops_crops_and_records_why(e2e):
    R, _ = e2e
    plain, occ = R["tasks"]["T2_sprite_sem"]["hparams"], R["tasks"]["T2_sprite_sem_occ"]["hparams"]
    assert all(occ["n_crops"][s] <= plain["n_crops"][s] for s in plain["n_crops"])
    # the per-frame crop cap refills from the remaining candidates, so counts can stay equal; the stats show what was removed
    a = occ["occ_stats"]["train"]["srcA"]
    assert a["low_visible_frac"] > 0 and a["with_info"] > 0 and a["kept"] + a["low_visible_frac"] == a["considered"] and a["kept"] < a["considered"]
    assert "srcB" in occ["occ_stats"]["train"] and "low_visible_frac" not in occ["occ_stats"]["train"]["srcB"]  # srcB has no visibility info
    assert "occ_filter" in occ and "occ_filter" not in plain


def test_t4_tiers(e2e):
    R, _ = e2e
    r = R["tasks"]["T4_near_dup"]["results"]
    assert set(Fe.AUG_KINDS + Fe.HARD_KINDS + ("mild_all", "hard_all")) <= set(r)
    assert r["hard_all"]["random"]["n_queries"] == len(Fe.HARD_KINDS) * r["rescale"]["random"]["n_queries"]
    assert r["mild_all"]["random"]["n_queries"] == len(Fe.AUG_KINDS) * r["rescale"]["random"]["n_queries"]
    # toy images are smooth blobs, so hashes survive mild changes
    assert r["mild_all"]["phash_hamming"]["R@1"] >= r["mild_all"]["random"]["R@1"]


def test_report_renders_new_sections(e2e, tmp_path):
    _, out = e2e
    md = tmp_path / "r.md"
    assert cli.main(["report", str(out / "results.json"), "--out", str(md)]) == 0
    t = md.read_text()
    for h in ("T1_norm (", "T1_norm_stretch (", "T2_sprite_sem_occ (", "T4_near_dup, mild tier", "T4_near_dup, hard tier", "T1 raw vs normalised", "occlusion filter: what it removed"):
        assert h in t, h


def test_new_tasks_same_seed_identical(fake, tmp_path, e2e):
    R, _ = e2e
    R2, _ = _run(fake, tmp_path, "again")
    strip = lambda r: {k: {kk: vv for kk, vv in v.items() if kk != "_seconds"} for k, v in r["tasks"].items()}
    assert strip(R) == strip(R2)


def test_resume_skips_finished_tasks(fake, tmp_path):
    R, out = _run(fake, tmp_path, "part", extra=["--tasks", "T3_game_retrieval", "T5_style_cluster"])
    R.pop("finished")
    json.dump(R, open(out / "results.json", "w"))
    before = R["tasks"]["T3_game_retrieval"]
    rc = cli.main(_args(fake) + ["run", "--scale", "smoke", "--workers", "2", "--out", str(out), "--cache", str(tmp_path / "feat"), "--resume", "--tasks", "T3_game_retrieval", "T5_style_cluster", "T4_near_dup"])
    assert rc == 0
    R2 = json.load(open(out / "results.json"))
    assert "finished" in R2 and R2["tasks"]["T3_game_retrieval"] == before and "T4_near_dup" in R2["tasks"]
    assert "resume: keeping finished tasks" in (out / "run.log").read_text()
    # a finished run is left alone
    assert cli.main(_args(fake) + ["run", "--scale", "smoke", "--out", str(out), "--cache", str(tmp_path / "feat"), "--resume"]) == 0
    assert "already finished" in (out / "run.log").read_text()


def test_v1_runs_are_read_only_inputs_to_report(e2e, tmp_path):
    """A v1-format result (no bench key, T4 `all`) still renders next to a v1.1 result."""
    R, out = e2e
    old = json.loads(json.dumps(R))
    old["config"].pop("bench"); old["config"]["version"] = "0.1.0"
    for t in ("T1_norm", "T1_norm_stretch", "T2_sprite_sem_occ"):
        old["tasks"].pop(t)
    nd = old["tasks"]["T4_near_dup"]["results"]
    old["tasks"]["T4_near_dup"]["results"] = {k: v for k, v in nd.items() if k in Fe.AUG_KINDS}
    old["tasks"]["T4_near_dup"]["results"]["all"] = nd["mild_all"]
    p = tmp_path / "old.json"; json.dump(old, open(p, "w"))
    md = tmp_path / "both.md"
    assert cli.main(["report", str(p), str(out / "results.json"), "--out", str(md)]) == 0
    t = md.read_text()
    assert "Benchmark v1.0" in t and "Benchmark v1.3" in t and "Protocol check" in t and "0 differ" in t
