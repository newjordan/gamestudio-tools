"""Integration test for examples/showcase-godot: rebuild assets from kit generators,
then (when GODOT_BIN is set) import and run the main scene headless and assert
wall collision stops the player.
"""
import os, shutil, stat, subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_SRC = ROOT / "examples" / "showcase-godot"
AUTHOR_FILES = ("project.godot", "import_rules.json", "build_showcase.sh",
                "bake_map.py", "stamp_tile.py")
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


def test_showcase_build_assets(tmp_path):
    """Regenerate the showcase from kit tools only (no Godot required)."""
    dst = tmp_path / "showcase"
    _copy_authored(dst)
    env = _isolate(tmp_path)
    env.pop("GODOT_BIN", None)
    r = _build(dst, env, timeout=120)
    assert r.returncode == 0, r.stdout
    for rel in (
        "art/tiles.png", "art/tiles.tres", "art/tiles_wang.json", "art/cells.json",
        "art/dungeon.json", "art/map_colliders.json", "art/player.png",
        "art/player_frames.tres", "art/walk_clips.json", "sfx/step.wav",
        "font/label.fnt", "font/label.png", "art/tiles.png.import", "sfx/step.wav.import",
    ):
        assert (dst / rel).is_file(), rel
    tres = (dst / "art/tiles.tres").read_text(encoding="utf-8")
    assert "7:5/0/physics_layer_0/polygon_0/points" in tres  # tile 47, solid wall
    assert "terrain_set_0" in tres
    frames = (dst / "art/player_frames.tres").read_text(encoding="utf-8")
    assert '&"walk"' in frames
    cells = (dst / "art/cells.json").read_text(encoding="utf-8")
    assert '"wall_id"' not in cells  # baked cells, not the flag
    assert '"spawn"' in cells and '"wall_dir"' in cells
    assert (dst / "font/label.fnt").read_text(encoding="utf-8").startswith("info face=")
    # scratch work must not be left behind; this test does not launch Godot
    assert not (dst / "art/work").exists()
    assert not (dst / ".godot").exists()


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_showcase_godot_collision_and_preview(tmp_path):
    dst = tmp_path / "showcase"
    _copy_authored(dst)
    env = _isolate(tmp_path)
    env["GODOT_BIN"] = godot_bin()
    r = _build(dst, env, timeout=180)
    assert r.returncode == 0, r.stdout
    # import (build already imported when Godot ran; repeat so the test is explicit)
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
    assert "GST_SHOWCASE_OK" in ver.stdout, ver.stdout
    can_render = bool(env.get("DISPLAY")) or bool(shutil.which("xvfb-run"))
    gif = dst / "preview" / "showcase.gif"
    if can_render:
        assert gif.is_file(), "expected preview/showcase.gif when a display or xvfb-run is available\n" + r.stdout
        assert gif.read_bytes()[:6] in (b"GIF87a", b"GIF89a")
        for name in ("shot_08.png", "shot_16.png", "shot_24.png"):
            shot = dst / "preview" / name
            assert shot.is_file() and shot.stat().st_size > 500, name
    else:
        print("no DISPLAY or xvfb-run; skipped preview GIF assert")
