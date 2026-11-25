"""Integration test for examples/showcase-platformer: rebuild assets from kit
generators, validate jump-arc gaps, then (when GODOT_BIN is set) import and run
a scripted jump across a gap and assert landing.
"""
import json, os, shutil, stat, subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_SRC = ROOT / "examples" / "showcase-platformer"
AUTHOR_FILES = ("project.godot", "import_rules.json", "build_showcase.sh", "bake_level.py")
AUTHOR_DIRS = ("scenes", "scripts")


def godot_bin():
    p = os.environ.get("GODOT_BIN") or ""
    return p if p and os.path.isfile(p) and os.access(p, os.X_OK) else ""


def _isolate(tmp_path):
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".local" / "share").mkdir(parents=True)
    (home / ".cache").mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["GST_ROOT"] = str(ROOT)
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    env.setdefault("GALLIUM_DRIVER", "llvmpipe")
    return env


def _copy_authored(dst: Path) -> None:
    dst.mkdir(parents=True)
    for name in AUTHOR_FILES:
        shutil.copy2(SHOWCASE_SRC / name, dst / name)
    (dst / "build_showcase.sh").chmod((dst / "build_showcase.sh").stat().st_mode | stat.S_IXUSR)
    for name in AUTHOR_DIRS:
        shutil.copytree(SHOWCASE_SRC / name, dst / name)


def _build(dst: Path, env: dict, timeout=180) -> subprocess.CompletedProcess:
    r = subprocess.run([str(dst / "build_showcase.sh")], cwd=str(dst), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, timeout=timeout)
    return r


def test_showcase_platformer_build_assets(tmp_path):
    """Regenerate the platformer from kit tools only (no Godot required)."""
    dst = tmp_path / "showcase"
    _copy_authored(dst)
    env = _isolate(tmp_path)
    env.pop("GODOT_BIN", None)
    r = _build(dst, env, timeout=120)
    assert r.returncode == 0, r.stdout
    for rel in (
        "art/tiles.png", "art/tiles.tres", "art/level.json", "art/cells.json",
        "art/colliders.json", "art/jump_gap1.json", "art/jump_gap2.json",
        "art/player.png", "art/player_frames.tres", "art/walk_clips.json",
        "art/coin.png", "art/parallax_far.png", "art/parallax_mid.png",
        "art/parallax_near.png", "sfx/coin.wav", "font/label.fnt", "font/label.png",
        "preview/parallax.gif", "art/tiles.png.import", "sfx/coin.wav.import",
    ):
        assert (dst / rel).is_file(), rel + "\n" + r.stdout
    tres = (dst / "art/tiles.tres").read_text(encoding="utf-8")
    assert "one_way = true" in tres
    assert "physics_layer_0/polygon_0/points" in tres
    cells = json.loads((dst / "art/cells.json").read_text(encoding="utf-8"))
    assert cells["gravity"] == 800 and cells["jump_v"] == 220 and cells["speed"] == 120
    assert len(cells["gaps"]) == 2
    level = json.loads((dst / "art/level.json").read_text(encoding="utf-8"))
    names = [l["name"] for l in level["layers"]]
    assert "ground" in names and "platforms" in names
    for i, g in enumerate(cells["gaps"], start=1):
        rec = json.loads((dst / f"art/jump_gap{i}.json").read_text(encoding="utf-8"))
        assert rec["out_of_bounds"] is False
        assert rec["landed"] is True
        x, y = rec["end"]
        assert g["land_min"] <= x < g["land_max"]
        assert g["floor_y"] - 1 <= y < g["floor_y"] + 16 + 1
    frames = (dst / "art/player_frames.tres").read_text(encoding="utf-8")
    assert '&"walk"' in frames
    fnt = (dst / "font/label.fnt").read_text(encoding="utf-8")
    assert fnt.startswith("info face=")
    gif = (dst / "preview/parallax.gif").read_bytes()
    assert gif[:6] in (b"GIF87a", b"GIF89a")
    assert not (dst / "art/work").exists()
    assert not (dst / ".godot").exists()
    # 3-tile (48 px) gaps between the takeoff tile's right edge and the far platform
    for g in cells["gaps"]:
        takeoff_right = (int(g["takeoff"][0]) // 16 + 1) * 16
        assert g["land_min"] - takeoff_right == 48


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_showcase_platformer_jump_and_preview(tmp_path):
    dst = tmp_path / "showcase"
    _copy_authored(dst)
    env = _isolate(tmp_path)
    env["GODOT_BIN"] = godot_bin()
    r = _build(dst, env, timeout=240)
    assert r.returncode == 0, r.stdout
    imp = subprocess.run(
        [godot_bin(), "--headless", "--path", str(dst), "--import", "--quit"],
        cwd=str(dst), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=120,
    )
    assert imp.returncode == 0, imp.stdout
    ver = subprocess.run(
        [godot_bin(), "--headless", "--path", str(dst), "--", "--verify"],
        cwd=str(dst), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=60,
    )
    assert ver.returncode == 0, ver.stdout
    assert "GST_PLATFORMER_OK" in ver.stdout, ver.stdout
    can_render = bool(env.get("DISPLAY")) or bool(shutil.which("xvfb-run"))
    gif = dst / "preview" / "showcase.gif"
    if can_render:
        assert gif.is_file(), "expected preview/showcase.gif when a display or xvfb-run is available\n" + r.stdout
        assert gif.read_bytes()[:6] in (b"GIF87a", b"GIF89a")
        for name in ("shot_12.png", "shot_24.png", "shot_36.png"):
            shot = dst / "preview" / name
            assert shot.is_file() and shot.stat().st_size > 500, name
    else:
        print("no DISPLAY or xvfb-run; skipped preview GIF assert")
