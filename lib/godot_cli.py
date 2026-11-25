"""Run the official / configured Godot 4 editor headless, with an isolated HOME."""
from __future__ import annotations

import os
import subprocess
import tempfile


def find_godot(explicit=None) -> str:
    p = explicit or os.environ.get("GODOT_BIN") or ""
    return p if p and os.path.isfile(p) and os.access(p, os.X_OK) else ""


def isolated_env(home: str, base=None) -> dict:
    env = (base or os.environ).copy()
    os.makedirs(os.path.join(home, ".config"), exist_ok=True)
    os.makedirs(os.path.join(home, ".local", "share"), exist_ok=True)
    os.makedirs(os.path.join(home, ".cache"), exist_ok=True)
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
    env["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
    env["XDG_CACHE_HOME"] = os.path.join(home, ".cache")
    return env


def run(godot, project, args, timeout=90, env=None, home=None):
    """Run Godot --headless --path project with extra args. Returns CompletedProcess."""
    if home is None:
        home = tempfile.mkdtemp(prefix="gst-godot-home-")
        own_home = True
    else:
        own_home = False
    try:
        e = isolated_env(home, env)
        cmd = [godot, "--headless", "--path", project] + list(args)
        return subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=e, timeout=timeout, text=True,
        )
    finally:
        if own_home:
            import shutil
            shutil.rmtree(home, ignore_errors=True)
