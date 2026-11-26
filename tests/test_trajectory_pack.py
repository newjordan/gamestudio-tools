"""The committed trajectory pack is real captured gst output, not a sketch.

These checks read the JSONL shards. They do not re-run the catalog. One short
trajectory is re-executed to prove generate.py --verify still matches.
"""
import importlib.util
import json
import os
import shlex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, "training_pack", "trajectories")
SHARDS = os.path.join(PACK, "shards")
FAMILIES = {
    "animation", "audio", "data", "dialogue", "fonts", "godot",
    "images", "loc", "maps", "mesh", "sprites", "terrain",
}
KINDS = {"act", "miss", "fix", "verify"}


def _records():
    out = []
    names = sorted(n for n in os.listdir(SHARDS) if n.endswith(".jsonl"))
    assert names, "no trajectory shards"
    for name in names:
        path = os.path.join(SHARDS, name)
        size = os.path.getsize(path)
        assert size < 5_000_000, "%s is %d bytes" % (name, size)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def _generate():
    path = os.path.join(PACK, "generate.py")
    spec = importlib.util.spec_from_file_location("traj_generate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pack_counts_and_shape():
    records = _records()
    stats = json.load(open(os.path.join(PACK, "stats.json"), encoding="utf-8"))
    assert len(records) >= 300
    assert stats["trajectory_count"] == len(records)
    assert stats["kit_version"] == open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))
    recovery = [r for r in records if r["recovery"]]
    frac = len(recovery) / len(records)
    assert 0.12 <= frac <= 0.18
    assert stats["recovery_count"] == len(recovery)
    assert stats["recovery_fraction"] == round(frac, 4)
    assert set(stats["primary_family"]) == FAMILIES
    assert sum(stats["primary_family"].values()) == len(records)
    assert set(stats["families_covered"]) == FAMILIES
    assert stats["step_count"] == sum(len(r["steps"]) for r in records)
    assert os.path.isfile(os.path.join(PACK, "dropped.jsonl"))
    dropped = [json.loads(l) for l in open(os.path.join(PACK, "dropped.jsonl"), encoding="utf-8") if l.strip()]
    assert stats["dropped_count"] == len(dropped)
    for row in dropped:
        assert row.get("reason") and row.get("id")

    by_tool_steps = {}
    by_tool_traj = {}
    for rec in records:
        assert rec["request"] and rec["primary_family"] in FAMILIES
        assert rec["steps"] and len(rec["steps"]) >= 2
        assert rec["steps"][-1]["kind"] == "verify"
        if rec["recovery"]:
            assert rec["steps"][0]["kind"] == "miss" and rec["steps"][0]["exit_code"] != 0
            assert rec["steps"][1]["kind"] == "fix"
            assert rec["steps"][0]["exit_code"] != 0
            assert "{error}" not in rec["steps"][1]["reasoning"]
        seen = []
        for i, step in enumerate(rec["steps"]):
            assert step["index"] == i
            assert step["kind"] in KINDS
            assert step["reasoning"]
            assert step["command"] == "gst " + shlex.join(step["argv"])
            assert isinstance(step["exit_code"], int)
            assert isinstance(step["stdout"], str) and isinstance(step["stderr"], str)
            blob = step["stdout"] + step["stderr"]
            assert "/tmp/" not in blob
            assert ROOT not in blob
            for f in step["files"]:
                assert len(f["sha256"]) == 64 and all(c in "0123456789abcdef" for c in f["sha256"])
                assert isinstance(f["bytes"], int) and f["bytes"] >= 0
                assert not os.path.isabs(f["path"])
                assert "{project}" not in f["path"]
            if step["argv"][0] not in seen:
                seen.append(step["argv"][0])
            by_tool_steps[step["argv"][0]] = by_tool_steps.get(step["argv"][0], 0) + 1
        assert rec["tools"] == seen
        for tool in seen:
            by_tool_traj[tool] = by_tool_traj.get(tool, 0) + 1
        for fam in rec["families"]:
            assert fam in FAMILIES
    assert stats["tools_covered"] == len(by_tool_traj)
    for tool, counts in stats["by_tool"].items():
        assert counts["steps"] == by_tool_steps[tool]
        assert counts["trajectories"] == by_tool_traj[tool]


def test_reverify_one_trajectory():
    records = _records()
    rec = next(r for r in records if r["id"] == "sprites-pixel-lint")
    problems = _generate().verify_record(rec)
    assert problems == []
