"""Version 2.4.0: regression tests for kit bugs found while building
examples/sample-game-full, plus the sample game's own checks (self-contained:
the sample game ships its generated project; Godot steps need GODOT_BIN)."""
import hashlib, json, os, re, shutil, struct, subprocess, sys, wave

import pytest

import ase_to_godot
import godot_import_presets
from test_batch31 import godot_bin, _isolate
from test_v21 import write_ase_frames

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "examples", "sample-game-full")


def _wav(path, frames=2000, loop=None):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", (i * 37) % 2000 - 1000) for i in range(frames)))
    if loop:
        smpl = struct.pack("<9I", 0, 0, 45351, 60, 0, 0, 0, 1, 0) + struct.pack("<6I", 0, 0, loop[0], loop[1], 0, 0)
        data = bytearray(open(path, "rb").read())
        data += b"smpl" + struct.pack("<I", len(smpl)) + smpl
        data[4:8] = struct.pack("<I", len(data) - 8)
        open(path, "wb").write(bytes(data))


# ------------------------------------------------ bug 1: godot-import-presets WAV loop modes
def test_wav_loop_preset_keeps_embedded_loop_points(tmp_path):
    proj = tmp_path / "p"; (proj / "audio").mkdir(parents=True)
    (proj / "project.godot").write_text("config_version=5\n")
    _wav(proj / "audio" / "looped.wav", loop=(100, 1500))
    _wav(proj / "audio" / "plain.wav")
    _wav(proj / "audio" / "shot.wav", loop=(10, 20))
    rules = tmp_path / "r.json"
    rules.write_text(json.dumps({"rules": [{"glob": "audio/shot.wav", "preset": "wav-oneshot"},
                                           {"glob": "audio/*.wav", "preset": "wav-loop"}]}))
    assert godot_import_presets.main([str(proj), "-r", str(rules)]) == 0
    imp = lambda n: (proj / "audio" / (n + ".wav.import")).read_text()
    # 2.3.1 wrote Forward (2) for every wav-loop file, discarding wav-loop-meta's points,
    # and Detect (0) for one-shots, so a stray smpl chunk looped a one-shot.
    assert "edit/loop_mode=0" in imp("looped")        # Detect From WAV: honour smpl
    assert "edit/loop_mode=2" in imp("plain")         # no smpl: loop the whole file
    assert "edit/loop_mode=1" in imp("shot")          # Disabled
    assert godot_import_presets.wav_has_loop(str(proj / "audio" / "looped.wav"))
    assert not godot_import_presets.wav_has_loop(str(proj / "audio" / "plain.wav"))
    assert not godot_import_presets.wav_has_loop(str(rules))


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_wav_loop_preset_loop_points_reach_godot(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    (proj / "project.godot").write_text("config_version=5\n")
    _wav(proj / "m.wav", loop=(100, 1500))
    _wav(proj / "s.wav", loop=(10, 20))
    rules = tmp_path / "r.json"
    rules.write_text(json.dumps({"rules": [{"glob": "s.wav", "preset": "wav-oneshot"},
                                           {"glob": "*.wav", "preset": "wav-loop"}]}))
    assert godot_import_presets.main([str(proj), "-r", str(rules)]) == 0
    (proj / "t.gd").write_text('extends SceneTree\nfunc _init():\n'
                               '	for n in ["m", "s"]:\n'
                               '		var w: AudioStreamWAV = load("res://%s.wav" % n)\n'
                               '		print("WAV ", n, " ", w.loop_mode, " ", w.loop_begin, " ", w.loop_end)\n'
                               '	quit()\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env,
                   capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://t.gd"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    assert "WAV m 1 100 1500" in r.stdout, r.stdout      # LOOP_FORWARD with the smpl points
    assert "WAV s 0 " in r.stdout, r.stdout              # LOOP_DISABLED


# ------------------------------------------------ bug 2: ase-to-godot default res:// path
def test_ase_to_godot_default_res_follows_frames_folder(tmp_path, capsys):
    colors = [(255, 0, 0, 255), (0, 255, 0, 255)]
    src = write_ase_frames(tmp_path / "hero.ase", 2, 2, colors, [100, 100], [("walk", 0, 1, 0, 0)])
    proj = tmp_path / "game"; (proj / "art").mkdir(parents=True)
    (proj / "project.godot").write_text("config_version=5\n")
    # 2.3.1 wrote res://frame_0000.png by default although frames go to <out>_frames.
    assert ase_to_godot.main([str(src), "-o", str(proj / "art" / "hero.tres")]) == 0
    text = (proj / "art" / "hero.tres").read_text()
    assert 'path="res://art/hero_frames/frame_0000.png"' in text
    assert ase_to_godot.main([str(src), "-o", str(tmp_path / "loose.tres")]) == 0
    assert 'path="res://loose_frames/frame_0000.png"' in (tmp_path / "loose.tres").read_text()
    assert "no project.godot" in capsys.readouterr().err
    assert ase_to_godot.main([str(src), "-o", str(tmp_path / "x.tres"), "--res", "res://f/"]) == 0
    assert 'path="res://f/frame_0000.png"' in (tmp_path / "x.tres").read_text()
    assert ase_to_godot.default_res(str(proj)) == "res://"


# ------------------------------------------------ sample game
def test_sample_game_readme_maps_every_generated_asset():
    readme = open(os.path.join(GAME, "README.md")).read()
    build = open(os.path.join(GAME, "build.sh")).read()
    used = set(re.findall(r"^\s*(?:for .*; do )?gst ([a-z0-9-]+)", build, re.M))
    assert {"map-to-godot", "map-objects-to-godot", "tile-colliders-to-godot", "nav-to-godot", "ase-to-godot",
            "hitbox-to-godot", "nine-slice-to-godot", "font-to-godot", "loc-to-godot", "data-to-godot",
            "wav-loop-meta", "godot-import-presets"} <= used
    for tool in used:
        assert "`gst %s" % tool in readme, tool
    gen = []
    for sub in ("art", "levels", "ui", "audio", "data", "i18n"):
        for dp, _, fs in os.walk(os.path.join(GAME, "project", sub)):
            gen += [f for f in fs if not f.endswith((".import", ".uid")) and not re.match(r"frame_\d{4}\.png$", f)]
    for f in gen:
        pat = re.sub(r"[123]", "N", f)
        assert f in readme or pat in readme, f
    assert "## Usage" in readme and "## Source and licence" in readme and "## Known gaps" in readme


def _copy_game(tmp_path):
    dst = tmp_path / "sample-game-full"
    shutil.copytree(GAME, dst, ignore=shutil.ignore_patterns(".godot", "work", "media", "*.uid", "__pycache__"))
    return dst


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_sample_game_imports_clean_and_autoplay_wins(tmp_path):
    proj = _copy_game(tmp_path) / "project"
    env = _isolate(tmp_path)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    assert not re.search(r"ERROR|SCRIPT ERROR", r.stdout), r.stdout[-2000:]
    for loc in ("en", "de"):
        r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--fixed-fps", "60", "--",
                            "--autoplay", "--timeout=90", "--locale=" + loc], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
        out = r.stdout
        assert r.returncode == 0, out[-2000:]
        assert not re.search(r"ERROR|still in use", out), out[-2000:]
        assert "tr_en=Gem Runner tr_de=Edelstein-Lauf" in out and "enemies=slime,slime_red" in out
        for marker in ("SAMPLE_GAME_LEVEL 3", "SAMPLE_GAME_NAV_OK level=3", "SAMPLE_GAME_GEM level=3",
                       "SAMPLE_GAME_WIN gems=3", "SAMPLE_GAME_DONE"):
            assert marker in out, (marker, out[-2000:])


def _digest(root):
    h = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".import", ".uid")):
                continue
            p = os.path.join(dp, f)
            h[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h


def test_sample_game_build_is_reproducible(tmp_path):
    game = _copy_game(tmp_path)
    env = dict(os.environ, GST_ROOT=ROOT)
    if godot_bin():
        env["GODOT_BIN"] = godot_bin()
    r = subprocess.run(["bash", str(game / "build.sh")], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:]
    assert "FAIL" not in r.stdout
    # without Godot, loc-to-godot writes Translation .tres fallbacks instead of official binaries
    for sub in ("art", "levels", "ui", "audio", "data") + (("i18n",) if godot_bin() else ()):
        want = _digest(os.path.join(GAME, "project", sub))
        got = _digest(str(game / "project" / sub))
        assert got == want, sub
