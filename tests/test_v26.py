"""Version 2.6.0: regressions for kit bugs found while building
examples/sample-towerdefense (Reed Causeway), plus the sample's own checks.
Self-contained bug tests write their inputs here. The sample ships its generated
project. Godot steps need GODOT_BIN.
"""
import hashlib, json, os, re, shutil, subprocess

import pytest

import anim_retarget_fps
import loc_check
import loc_placeholder_lint
from test_batch31 import godot_bin, _isolate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "examples", "sample-towerdefense")
_TOOL_RX = re.compile(r"^\s*(?:for .*; do )?gst ([a-z0-9-]+)", re.M)


def test_anim_retarget_fps_accepts_anim_meta_dict(tmp_path):
    # anim-from-folder / anim-pingpong / anim-meta write clips as an object keyed by name.
    # 2.5.0 only accepted a list, so a pipeline of those tools could not retarget fps.
    doc = {"clips": {"walk": {"frames": ["walk_0", "walk_1", "walk_2", "walk_3"], "fps": 8, "loop": True}}}
    (tmp_path / "in.json").write_text(json.dumps(doc), encoding="utf-8")
    assert anim_retarget_fps.main([str(tmp_path / "in.json"), "-o", str(tmp_path / "out.json"), "--fps", "10"]) == 0
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    walk = out["clips"]["walk"]
    assert walk["fps"] == 10
    assert walk["frames"] == ["walk_0", "walk_1", "walk_2", "walk_3"]
    assert len(walk["durations"]) == 4 and all(d > 0 for d in walk["durations"])


def _plural_csv(tmp_path):
    # Branch wording is translated; the argument name is the placeholder.
    text = (
        "id,en,de,fr\n"
        'wave_n,"{n, plural, one {# wave} other {# waves}}","{n, plural, one {# Welle} other {# Wellen}}","{n, plural, one {# vague} other {# vagues}}"\n'
        'greet,"Hello {name}","Hallo {name}","Bonjour {name}"\n'
    )
    p = tmp_path / "loc.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_loc_check_ignores_icu_plural_branch_wording(tmp_path):
    p = _plural_csv(tmp_path)
    assert loc_check.main([str(p)]) == 0
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "id,en,de\n"
        'wave_n,"{n, plural, one {# wave} other {# waves}}","{m, plural, one {# Welle} other {# Wellen}}"\n',
        encoding="utf-8",
    )
    assert loc_check.main([str(bad)]) == 1
    nested = tmp_path / "nested.csv"
    nested.write_text(
        "id,en,de\n"
        'line,"{n, plural, one {{item}} other {{item}s}}","{n, plural, one {{item}} other {{item}e}}"\n',
        encoding="utf-8",
    )
    assert loc_check.main([str(nested)]) == 0
    dropped = tmp_path / "dropped.csv"
    dropped.write_text(
        "id,en,de\n"
        'line,"{n, plural, one {{item}} other {{item}s}}","{n, plural, one {#} other {#}}"\n',
        encoding="utf-8",
    )
    assert loc_check.main([str(dropped)]) == 1


def test_loc_placeholder_lint_ignores_icu_plural_branch_wording(tmp_path):
    assert loc_placeholder_lint.main([str(_plural_csv(tmp_path))]) == 0


def _tools(path):
    return set(_TOOL_RX.findall(open(path, encoding="utf-8").read()))


def test_towerdefense_readme_maps_every_generated_asset():
    readme = open(os.path.join(GAME, "README.md"), encoding="utf-8").read()
    used = _tools(os.path.join(GAME, "build.sh"))
    others = _tools(os.path.join(ROOT, "examples", "sample-topdown", "build.sh")) | _tools(
        os.path.join(ROOT, "examples", "sample-game-full", "build.sh"))
    new = used - others
    assert len(used) >= 100, len(used)
    assert len(new) >= 50, sorted(new)
    assert {"anim-to-godot", "anim-retarget-fps", "curve-gen", "loop-xfade", "loc-plurals",
            "wfc-tiles", "sprite-stack", "wav-dc-remove"} <= new
    for tool in used:
        assert "`gst %s" % tool in readme, tool
    for sub in ("art", "levels", "ui", "audio", "data", "i18n"):
        base = os.path.join(GAME, "project", sub)
        if not os.path.isdir(base):
            continue
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.endswith((".import", ".uid")):
                    continue
                assert f in readme, f
    assert "## Usage" in readme and "## Source and licence" in readme and "## Known gaps" in readme
    loc = open(os.path.join(GAME, "data", "loc.csv"), encoding="utf-8").read()
    for ch in "äöüßéèàçêœî":
        assert ch in loc, ch


def _copy_game(tmp_path):
    dst = tmp_path / "sample-towerdefense"
    shutil.copytree(GAME, dst, ignore=shutil.ignore_patterns(".godot", "work", "media", "*.uid", "__pycache__"))
    return dst


def _digest(root):
    h = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".import", ".uid")):
                continue
            p = os.path.join(dp, f)
            h[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h


def test_towerdefense_build_is_reproducible(tmp_path):
    game = _copy_game(tmp_path)
    env = dict(os.environ, GST_ROOT=ROOT, HOME=os.environ.get("HOME") or "/home/ubuntu")
    if godot_bin():
        env["GODOT_BIN"] = godot_bin()
    r = subprocess.run(["bash", str(game / "build.sh")], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=420)
    assert r.returncode == 0, r.stdout[-3000:]
    for sub in ("art", "levels", "ui", "audio", "data") + (("i18n",) if godot_bin() else ()):
        want = _digest(os.path.join(GAME, "project", sub))
        got = _digest(str(game / "project" / sub))
        assert got == want, (sub, sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))[:12])


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_towerdefense_imports_clean_and_autoplay_wins(tmp_path):
    proj = _copy_game(tmp_path) / "project"
    env = _isolate(tmp_path)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    assert not re.search(r"ERROR|SCRIPT ERROR", r.stdout), r.stdout[-2000:]
    outs = []
    for loc in ("en", "de"):
        r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--fixed-fps", "60", "--",
                            "--autoplay", "--locale=" + loc, "--save=user://reed_%s.json" % loc], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
        out = r.stdout
        assert r.returncode == 0, out[-2500:]
        assert not re.search(r"SCRIPT ERROR|ERROR:|still in use|TD_FAIL|TD_LEAK|NAV_FAIL", out), out[-2500:]
        assert "en=Reed Causeway" in out and "de=Schilfdamm" in out and "fr=Chaussée des Roseaux" in out
        for marker in ("INPUT_OK true actions=5 with_gamepad=5", "NAV_OK points=6",
                       "TD_WIN core=16 leaks=0 kills=34 gold=199 towers=8 frames=1506", "TD_DONE"):
            assert marker in out, (marker, out[-2000:])
        save = re.search(r"TD_DONE .* save=(.+)", out).group(1).strip()
        data = json.load(open(save))
        row = data[0]
        assert row["locale"] == loc and row["kills"] == 34 and row["leaks"] == 0
        assert row["towers"] == 8 and row["seed"] == 11 and row["waves"] == 4 and row["core"] == 16
        outs.append([ln for ln in out.splitlines()
                     if ln.startswith(("TD_PLACE", "TD_WAVE", "TD_KILL", "TD_END", "TD_WIN", "NAV_OK"))])
    assert outs[0] == outs[1]
