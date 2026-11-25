"""Tests for the gst entry point, the bundle command and install.sh. Everything installs into pytest temp dirs
with HOME pointed at a temp dir; nothing touches the real PATH or home."""
import json, os, subprocess, sys, tarfile
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GST = os.path.join(ROOT, "gst"); INSTALL = os.path.join(ROOT, "install.sh")


def run(args, cwd=None, env=None, check=False):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=e)
    if check: assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r


def tool_dirs():
    return sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, d.replace("-", "_") + ".py")))


def test_every_tool_is_listed_documented_and_tested_by_name():
    out = run([sys.executable, GST, "list"], check=True).stdout
    dirs = tool_dirs(); assert len(dirs) >= 62
    for d in dirs:
        assert d in out
        assert os.path.exists(os.path.join(ROOT, d, "README.md")), f"{d} has no README"
        src = open(os.path.join(ROOT, d, "README.md")).read()
        assert "## Source and licence" in src and "## Usage" in src, f"{d} README is missing a section"
    assert f"{len(dirs)} tools" in out


def test_gst_runs_tools_and_passes_exit_codes(tmp_path):
    p = tmp_path / "l.png"
    r = run([sys.executable, GST, "lut-tool", "identity", "--size", "8", "-o", str(p)]); assert r.returncode == 0 and p.exists()
    r = run([sys.executable, GST, "help", "atlas-pack"]); assert r.returncode == 0 and "usage:" in r.stdout
    (tmp_path / "items.csv").write_text("id,price\na,-1\n")
    json.dump({"tables": {"items": {"file": "items.csv", "key": "id", "fields": {"id": {"type": "str"}, "price": {"type": "int", "min": 0}}}}}, open(tmp_path / "s.json", "w"))
    assert run([sys.executable, GST, "game-data-lint", str(tmp_path / "s.json")]).returncode == 1                         # the tool's own exit code comes through
    r = run([sys.executable, GST, "atlas-pak"]); assert r.returncode == 2 and "atlas-pack" in r.stderr                    # typo suggestion
    assert run([sys.executable, GST, "version"], check=True).stdout.startswith("gamestudio-tools ")
    assert run([sys.executable, GST, "doctor"]).returncode == 0
    c = run([sys.executable, GST, "completion", "bash"], check=True).stdout; assert "complete -F _gst gst" in c and "atlas-pack" in c and "doctor" in c
    assert run([sys.executable, GST, "info", "atlas-pack"], check=True).stdout.startswith("atlas-pack:")
    assert run([sys.executable, GST, "completion"]).returncode == 2
    assert run([sys.executable, GST]).returncode == 0
    r = run([sys.executable, GST, "wav-loop-meta", "show", str(tmp_path / "nope.wav")]); assert r.returncode != 0               # tool errors do not look like success


def test_bundle_is_reproducible_and_clean(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    ra = run([sys.executable, GST, "bundle", "-o", str(a)], check=True); run([sys.executable, GST, "bundle", "-o", str(b)], check=True)
    tgz = next(a.glob("*.tar.gz")); assert tgz.read_bytes() == next(b.glob("*.tar.gz")).read_bytes()                       # byte-identical
    digest = open(str(tgz) + ".sha256").read().split()[0]; assert digest in ra.stdout
    import hashlib; assert hashlib.sha256(tgz.read_bytes()).hexdigest() == digest
    names = tarfile.open(tgz).getnames(); top = names[0].split("/")[0]
    assert f"{top}/gst" in names and f"{top}/install.sh" in names and f"{top}/tests/test_gst.py" in names and f"{top}/atlas-pack/atlas_pack.py" in names
    assert not any("/samples/" in n or "__pycache__" in n or n.endswith((".tar.gz", ".sha256")) for n in names)
    mode = tarfile.open(tgz).getmember(f"{top}/gst").mode; assert mode & 0o111


def env(tmp):
    import site
    return {"HOME": str(tmp / "home"), "PYTHONUSERBASE": site.getuserbase()}      # keep finding pip --user packages after HOME moves


def test_install_dry_run_touches_nothing(tmp_path):
    (tmp_path / "home").mkdir(); before = sorted(os.listdir(tmp_path))
    r = run(["bash", INSTALL, "--dry-run", "--prefix", str(tmp_path / "prefix"), "--link-dir", str(tmp_path / "bin"), "--venv", "--with-tests"], env=env(tmp_path), check=True)
    assert "[dry-run]" in r.stdout and "venv" in r.stdout and sorted(os.listdir(tmp_path)) == before and not (tmp_path / "prefix").exists() and not (tmp_path / "bin").exists()
    assert os.listdir(tmp_path / "home") == []


def test_install_use_and_uninstall(tmp_path):
    (tmp_path / "home").mkdir(); pre, binp = tmp_path / "p", tmp_path / "bin"
    r = run(["bash", INSTALL, "--prefix", str(pre), "--link-dir", str(binp)], env=env(tmp_path), check=True)
    assert (pre / "gst").exists() and (pre / ".gst-install").exists() and (binp / "gst").exists()
    assert not (pre / "samples").exists() and not (pre / "tests").exists()                                               # lean by default
    out = run([str(binp / "gst"), "list"], env=env(tmp_path), check=True).stdout; assert "atlas-pack" in out
    p = tmp_path / "x.png"; run([str(binp / "gst"), "lut-tool", "identity", "-o", str(p)], env=env(tmp_path), check=True); assert p.exists()
    assert os.listdir(tmp_path / "home") == []                                                                           # nothing written to HOME
    # upgrade in place keeps working, --with-tests adds the tests
    run(["bash", INSTALL, "--prefix", str(pre), "--link-dir", str(binp), "--with-tests"], env=env(tmp_path), check=True); assert (pre / "tests" / "test_gst.py").exists()
    assert run([str(binp / "gst"), "test", "-k", "lut", "-q"], env=env(tmp_path)).returncode == 0
    r = run(["bash", INSTALL, "--uninstall", "--prefix", str(pre), "--link-dir", str(binp), "--dry-run"], env=env(tmp_path), check=True); assert pre.exists() and binp.joinpath("gst").exists()
    run(["bash", INSTALL, "--uninstall", "--prefix", str(pre), "--link-dir", str(binp)], env=env(tmp_path), check=True); assert not pre.exists() and not (binp / "gst").exists()


def test_install_refuses_unsafe_targets(tmp_path):
    (tmp_path / "home").mkdir()
    foreign = tmp_path / "foreign"; foreign.mkdir(); (foreign / "keep.txt").write_text("mine")
    assert run(["bash", INSTALL, "--prefix", str(foreign)], env=env(tmp_path)).returncode != 0 and (foreign / "keep.txt").read_text() == "mine" and not (foreign / "gst").exists()
    r = run(["bash", INSTALL, "--uninstall", "--prefix", str(foreign)], env=env(tmp_path)); assert r.returncode != 0 and (foreign / "keep.txt").exists()      # no marker: not ours
    assert run(["bash", INSTALL, "--prefix", "/"], env=env(tmp_path)).returncode != 0
    assert run(["bash", INSTALL, "--prefix", str(tmp_path / "home")], env=env(tmp_path)).returncode != 0
    assert run(["bash", INSTALL, "--bogus"], env=env(tmp_path)).returncode != 0
    binp = tmp_path / "bin"; binp.mkdir(); (binp / "gst").write_text("#!/bin/sh\necho not ours\n")
    r = run(["bash", INSTALL, "--prefix", str(tmp_path / "p2"), "--link-dir", str(binp)], env=env(tmp_path)); assert r.returncode != 0 and "not ours" in (binp / "gst").read_text()


def test_install_from_tarball(tmp_path):
    (tmp_path / "home").mkdir(); out = tmp_path / "rel"
    run([sys.executable, GST, "bundle", "-o", str(out)], check=True); tgz = next(out.glob("*.tar.gz"))
    pre = tmp_path / "t"; run(["bash", INSTALL, "--tarball", str(tgz), "--prefix", str(pre)], env=env(tmp_path), check=True)
    assert "sha256 verified" in run(["bash", INSTALL, "--tarball", str(tgz), "--prefix", str(pre)], env=env(tmp_path), check=True).stdout
    assert run([sys.executable, str(pre / "gst"), "version"], check=True).stdout.startswith("gamestudio-tools")
    bad = tmp_path / "bad.tar.gz"; bad.write_bytes(tgz.read_bytes()[:-5] + b"xxxxx"); open(str(bad) + ".sha256", "w").write(open(str(tgz) + ".sha256").read())
    r = run(["bash", INSTALL, "--tarball", str(bad), "--prefix", str(tmp_path / "t2")], env=env(tmp_path)); assert r.returncode != 0 and "mismatch" in r.stderr and not (tmp_path / "t2").exists()


def test_gst_list_search_and_categories():
    r = run([sys.executable, GST, "list"], check=True)
    assert "[maps]" in r.stdout and "[godot]" in r.stdout and "atlas-pack" in r.stdout
    dirs = tool_dirs(); assert f"{len(dirs)} tools" in r.stdout
    r = run([sys.executable, GST, "list", "--category", "godot"], check=True)
    listed = [ln.split()[0] for ln in r.stdout.splitlines() if ln and ln[0].isalpha()]
    assert "atlas-to-godot" in listed and "godot-tileset" in listed and "map-to-godot" in listed and "atlas-pack" not in listed
    assert f"{len(listed)} tools in category godot" in r.stdout
    r = run([sys.executable, GST, "list", "--category", "nope"]); assert r.returncode == 2
    r = run([sys.executable, GST, "categories"], check=True)
    assert "maps" in r.stdout and "audio" in r.stdout and f"{len(dirs)} tools" in r.stdout
    r = run([sys.executable, GST, "search", "atlas"], check=True)
    assert "atlas-pack" in r.stdout and "atlas-to-godot" in r.stdout and "tool(s) matched" in r.stdout
    r = run([sys.executable, GST, "search", "--category", "godot", "sprite"]); assert r.returncode == 0 and "atlas-to-godot" in r.stdout
    r = run([sys.executable, GST, "search", "zzzznotatool"]); assert r.returncode == 1
    r = run([sys.executable, GST, "search"]); assert r.returncode == 2
    r = run([sys.executable, GST, "bundle", "--help"]); assert r.returncode == 0 and "usage: gst bundle -o DIR" in r.stdout
    r = run([sys.executable, GST, "bundle"]); assert r.returncode == 2 and "usage: gst bundle -o DIR" in r.stderr
    # completion includes the new reserved words
    c = run([sys.executable, GST, "completion", "bash"], check=True).stdout
    assert "search" in c and "categories" in c and "docs" in c and "fuzz" in c
