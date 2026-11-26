import json, os, shutil
import pytest
from gbench import cli


def _args(fake):
    return ["--clean", fake["clean"], "--data-root", fake["root"], "--class-map", fake["class_map"]]


def _run(fake, tmp_path, name, seed=0):
    out = tmp_path / name
    rc = cli.main(_args(fake) + ["run", "--scale", "smoke", "--seed", str(seed), "--workers", "2", "--out", str(out), "--cache", str(tmp_path / f"feat_{name}")])
    assert rc == 0
    return json.load(open(out / "results.json")), out


def test_check_ok(fake):
    assert cli.main(_args(fake) + ["check"]) == 0


def test_end_to_end_and_determinism(fake, tmp_path):
    r1, out1 = _run(fake, tmp_path, "a")
    r2, _ = _run(fake, tmp_path, "b")
    assert set(r1["tasks"]) == set(cli.ALL_TASKS)
    strip = lambda r: {k: {kk: vv for kk, vv in v.items() if kk != "_seconds"} for k, v in r["tasks"].items()}
    assert strip(r1) == strip(r2), "same seed must give identical results"
    t1 = r1["tasks"]["T1_source_id"]["results"]
    # fake data: games have distinct colours, sources differ in texture -> colour kNN beats random on seen
    assert t1["test_seen"]["hist_knn_k1"]["acc"] >= t1["test_seen"]["random"]["acc"]
    assert t1["test_unseen_games"]["majority"]["n"] == t1["test_unseen"]["majority"]["n"]  # all fake unseen games are whole-game
    assert "logreg_size_only" in t1["test_seen"] and "size_knn_k10" in t1["test_seen"]
    t2 = r1["tasks"]["T2_sprite_sem"]
    assert set(t2["hparams"]["classes"]) == {"character", "prop"}
    assert t2["results"]["test_seen"]["hist_knn_k1"]["acc"] > 0.9  # white vs black squares
    nd = r1["tasks"]["T4_near_dup"]["results"]
    assert nd["mild_all"]["phash_hamming"]["R@1"] >= nd["mild_all"]["random"]["R@1"]
    assert (out1 / "run.log").exists() and "task T5_style_cluster done" in (out1 / "run.log").read_text()
    md = tmp_path / "R.md"
    assert cli.main(["report", str(out1 / "results.json"), "--out", str(md)]) == 0
    txt = md.read_text()
    for t in cli.ALL_TASKS:
        assert t in txt
    # cache reuse gives the same numbers
    r3, _ = _run(fake, tmp_path, "a")
    assert strip(r3) == strip(r1)


def test_check_fails_on_leak(fake, tmp_path):
    bad = tmp_path / "clean_bad"
    shutil.copytree(fake["clean"], bad)
    tr = open(bad / "splits_v1/train.jsonl").readlines()
    with open(bad / "splits_v1/test_unseen.jsonl", "a") as fh:
        fh.write(tr[0])
    args = ["--clean", str(bad), "--data-root", fake["root"], "--class-map", fake["class_map"]]
    assert cli.main(args + ["check"]) == 1
    assert cli.main(args + ["run", "--scale", "smoke", "--workers", "1", "--out", str(tmp_path / "x"), "--cache", str(tmp_path / "c")]) == 2


def test_tasks_listing(capsys):
    cli.main(["tasks"])
    assert "T1_source_id" in capsys.readouterr().out
