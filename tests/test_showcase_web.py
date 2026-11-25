"""Integration test for examples/showcase-web: rebuild assets from kit generators,
parse them with the reusable loader under Node, and (when CutyCapt / Xvfb is
available) screenshot the first frame of the served page.
"""
import json, os, shutil, socket, stat, subprocess, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_SRC = ROOT / "examples" / "showcase-web"
AUTHOR_FILES = ("index.html", "build_showcase.sh", "bake_room.py", "README.md")
AUTHOR_DIRS = ("js",)


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
    env.pop("GODOT_BIN", None)
    return env


def _copy_authored(dst: Path) -> None:
    dst.mkdir(parents=True)
    for name in AUTHOR_FILES:
        shutil.copy2(SHOWCASE_SRC / name, dst / name)
    (dst / "build_showcase.sh").chmod((dst / "build_showcase.sh").stat().st_mode | stat.S_IXUSR)
    for name in AUTHOR_DIRS:
        shutil.copytree(SHOWCASE_SRC / name, dst / name)


# Quiet-box builds finish in ~30s; 180s was enough until a loaded box made the
# same script time out. 600s plus one clean retry absorbs load spikes without
# hiding a genuine hang (two failures still fail the test).
BUILD_TIMEOUT = int(os.environ.get("GST_SHOWCASE_BUILD_TIMEOUT", "600"))


def _build(dst: Path, env: dict, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run([str(dst / "build_showcase.sh")], cwd=str(dst), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, timeout=BUILD_TIMEOUT if timeout is None else timeout)


def _not_uniform(im: Image.Image, tol=3) -> bool:
    colors = im.getcolors(maxcolors=256) or []
    if not colors:
        return True
    # a nearly-solid frame (one colour dominates all but `tol` counts of others)
    total = im.size[0] * im.size[1]
    top = max(c[0] for c in colors)
    return (total - top) > max(50, int(total * 0.002))


def test_showcase_web_build_and_parse(tmp_path):
    dst = tmp_path / "showcase"
    _copy_authored(dst)
    env = _isolate(tmp_path)
    try:
        r = _build(dst, env)
    except subprocess.TimeoutExpired:
        shutil.rmtree(dst)
        _copy_authored(dst)
        r = _build(dst, env)
    assert r.returncode == 0, r.stdout
    for rel in (
        "art/tiles.png", "art/level.json", "art/path.json", "art/player.png",
        "art/player.json", "sfx/coin.wav", "font/label.fnt", "font/label.png",
        "index.html", "js/gst-loader.js", "js/gst-loader.mjs",
    ):
        assert (dst / rel).is_file(), rel + "\n" + r.stdout
    assert not (dst / "art/work").exists()
    level = json.loads((dst / "art/level.json").read_text())
    names = [o.get("name") for l in level["layers"] if l.get("type") == "objectgroup"
             for o in l.get("objects") or []]
    assert "spawn" in names and "coin" in names
    path = json.loads((dst / "art/path.json").read_text())
    assert path["found"] is True and path["steps"] >= 2
    atlas = json.loads((dst / "art/player.json").read_text())
    frames = atlas["frames"]
    keys = list(frames) if isinstance(frames, dict) else [f.get("filename") for f in frames]
    assert "coin" in keys and "walk_01" in keys
    # atlas-sort --by name: coin before walk_*
    assert keys.index("coin") < keys.index("walk_01")
    fnt = (dst / "font/label.fnt").read_text(encoding="utf-8")
    assert fnt.startswith("info face=")

    node = shutil.which("node")
    assert node, "node is required to parse the loader and assets"
    pr = subprocess.run(
        [node, str(dst / "js" / "parse-check.mjs"), str(dst)],
        cwd=str(dst), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=30,
    )
    assert pr.returncode == 0, pr.stdout
    rec = json.loads(pr.stdout)
    assert rec["ok"] is True
    assert rec["map"]["width"] == 20 and rec["map"]["height"] == 10
    assert rec["wav"]["frames"] > 0 and rec["font"]["chars"] >= 10

    can_shot = bool(shutil.which("cutycapt")) and (
        bool(env.get("DISPLAY")) or bool(shutil.which("xvfb-run"))
    )
    if can_shot:
        # Prefer previews written by the build; otherwise capture the first frame here.
        shot = dst / "preview" / "shot_00.png"
        if not shot.is_file():
            shot = dst / "preview" / "first.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass
            class Rooted(Quiet):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(dst), **kwargs)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Rooted)
            Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html?preview=1&muted=1&step=0"
                raw = dst / "preview" / "_raw.png"
                args = ["cutycapt", f"--url={url}", f"--out={raw}",
                        "--delay=1500", "--min-width=640", "--min-height=360",
                        "--javascript=on", "--auto-load-images=on", "--max-wait=20000"]
                if env.get("DISPLAY") and shutil.which("cutycapt"):
                    cap = subprocess.run(args, cwd=str(dst), env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, timeout=40)
                else:
                    cap = subprocess.run(["xvfb-run", "-a", "-s", "-screen 0 800x600x24"] + args,
                                         cwd=str(dst), env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, timeout=40)
                assert cap.returncode == 0, cap.stdout
                im = Image.open(raw).convert("RGBA")
                im.crop((0, 0, 640, 360)).save(shot)
            finally:
                httpd.shutdown()
        im = Image.open(shot).convert("RGB")
        assert im.size[0] >= 320 and im.size[1] >= 180, im.size
        assert _not_uniform(im), "first frame looks nearly uniform (assets probably failed to draw)"
        gif = dst / "preview" / "showcase.gif"
        if gif.is_file():
            gim = Image.open(gif)
            assert gim.format == "GIF"
    else:
        print("no cutycapt + display/xvfb-run; skipped first-frame screenshot assert")
