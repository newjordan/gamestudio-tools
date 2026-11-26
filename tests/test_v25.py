"""Version 2.5.0: regression tests for kit bugs found while building
examples/sample-topdown (Ember Crypt), plus the sample's own checks.
Self-contained: inputs are written here; the sample ships its generated project;
Godot steps need GODOT_BIN."""
import hashlib, json, os, re, shutil, subprocess, sys

import pytest
from PIL import Image

import anim_from_folder
import asset_unused
import atlas_to_godot
import dungeon_gen
import map_to_godot
import map_reach
import nav_to_godot
from test_batch31 import godot_bin, _isolate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "examples", "sample-topdown")


def _run_godot_script(tmp_path, proj, script_text):
    (proj / "t.gd").write_text(script_text)
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "t.gd"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    return r.stdout


# ------------------------------------------------ bug 1: dungeon-gen JSON had no tileset
def test_dungeon_gen_json_is_a_usable_tiled_map(tmp_path, capsys):
    out = tmp_path / "d"
    assert dungeon_gen.main(["--mode", "bsp", "--size", "30x20", "--seed", "5", "-o", str(out)]) in (0, None)
    m = json.loads((tmp_path / "d.json").read_text())
    # 2.4.0 wrote "tilesets": [] so every kit consumer saw an empty or all-walkable map
    assert m["tilesets"] and m["tilesets"][0]["firstgid"] == 1
    ts = m["tilesets"][0]
    assert (tmp_path / ts["image"]).is_file() and ts["tilecount"] == 2
    wall = [t for t in ts.get("tiles", []) if t["id"] == 1][0]
    assert {"name": "solid", "type": "bool", "value": True} in wall["properties"]
    assert m["nextlayerid"] > len(m["layers"]) and all("id" in l for l in m["layers"])
    rooms = [l for l in m["layers"] if l["type"] == "objectgroup" and l["name"] == "rooms"][0]["objects"]
    assert len(rooms) >= 3 and all(o["type"] == "room" for o in rooms)
    props = {p["name"] for p in rooms[0]["properties"]}
    assert {"index", "cx", "cy", "w", "h"} <= props
    # the consumers now see walls: map-to-godot writes cells, map-reach finds blocked tiles
    assert map_to_godot.main([str(tmp_path / "d.json"), "-o", str(tmp_path / "d.tscn"),
                              "--write-tileset", str(tmp_path / "d_ts.tres"), "--res", "res://"]) in (0, None)
    assert "tile_map_data" in (tmp_path / "d.tscn").read_text()
    rep = tmp_path / "reach.json"
    map_reach.main([str(tmp_path / "d.json"), "--start", "%d,%d" % (rooms[0]["x"] // 16 + 1, rooms[0]["y"] // 16 + 1),
                    "--solid-ids", "2", "--json", str(rep)])
    r = json.loads(rep.read_text())
    assert 0 < r["walkable"] < 30 * 20 and r["reachable"] == r["walkable"]


# ------------------------------------------------ bug 2: atlas-to-godot dropped trim offsets
def _trimmed_atlas(tmp_path):
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for x in range(6):
        for y in range(4):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(tmp_path / "a.png")
    atlas = {"frames": {"run_0.png": {"frame": {"x": 0, "y": 0, "w": 6, "h": 4}, "rotated": False, "trimmed": True,
                                      "spriteSourceSize": {"x": 5, "y": 9, "w": 6, "h": 4},
                                      "sourceSize": {"w": 16, "h": 16}}},
             "meta": {"image": "a.png", "size": {"w": 8, "h": 8}}}
    (tmp_path / "a.json").write_text(json.dumps(atlas))
    return tmp_path / "a.json"


def test_atlas_to_godot_restores_trimmed_canvas(tmp_path, capsys):
    a = _trimmed_atlas(tmp_path)
    assert atlas_to_godot.main([str(a), "-o", str(tmp_path / "f.tres"), "--res", "res://a.png"]) in (0, None)
    t = (tmp_path / "f.tres").read_text()
    # 2.4.0 wrote only region = Rect2(0, 0, 6, 4): frames shrank to 6x4 and lost their 5,9 offset
    assert "region = Rect2(0, 0, 6, 4)" in t
    assert "margin = Rect2(5, 9, 10, 12)" in t
    assert atlas_to_godot.trim_margin({"spriteSourceSize": {"x": 0, "y": 0}, "sourceSize": {"w": 6, "h": 4}}, 6, 4) is None


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_atlas_to_godot_trimmed_frame_keeps_source_size_in_godot(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    (proj / "project.godot").write_text("config_version=5\n")
    a = _trimmed_atlas(proj)
    assert atlas_to_godot.main([str(a), "-o", str(proj / "f.tres"), "--res", "res://a.png"]) in (0, None)
    out = _run_godot_script(tmp_path, proj, 'extends SceneTree\nfunc _initialize():\n'
                            '\tvar sf: SpriteFrames = load("res://f.tres")\n'
                            '\tvar t: Texture2D = sf.get_frame_texture(sf.get_animation_names()[0], 0)\n'
                            '\tprint("SIZE %dx%d" % [t.get_width(), t.get_height()])\n\tquit()\n')
    assert "SIZE 16x16" in out, out[-1500:]


# ------------------------------------------------ bug 3: anim-from-folder --fps globs / repeats
def test_anim_from_folder_fps_accepts_globs_and_repeats(tmp_path, capsys):
    for clip in ("walk-down", "walk-up", "idle"):
        for i in range(2):
            Image.new("RGBA", (4, 4), (9, 9, 9, 255)).save(tmp_path / ("%s_%d.png" % (clip, i)))
    out = tmp_path / "clips.json"
    assert anim_from_folder.main([str(tmp_path), "-o", str(out), "--pattern", "{clip}_{frame}.png",
                                  "--default-fps", "8", "--fps", "walk-*=10", "--fps", "idle=4",
                                  "--once", "idl*"]) in (0, None)
    c = json.loads(out.read_text())["clips"]
    # 2.4.0 treated 'walk-*' as a literal clip name and kept only the last --fps flag
    assert c["walk-down"]["fps"] == 10 and c["walk-up"]["fps"] == 10
    assert c["idle"]["fps"] == 4 and c["idle"]["loop"] is False and c["walk-up"]["loop"] is True
    # exact names still win over globs
    assert anim_from_folder.main([str(tmp_path), "-o", str(out), "--pattern", "{clip}_{frame}.png",
                                  "--fps", "walk-*=10,walk-up=6"]) in (0, None)
    c = json.loads(out.read_text())["clips"]
    assert c["walk-up"]["fps"] == 6 and c["walk-down"]["fps"] == 10


# ------------------------------------------------ bug 4: asset-unused ignored project.godot and .fnt pages
def test_asset_unused_reads_project_godot_and_bmfont_pages(tmp_path, capsys):
    (tmp_path / "art").mkdir(); (tmp_path / "ui").mkdir(); (tmp_path / "i18n").mkdir()
    (tmp_path / "project.godot").write_text(
        'config_version=5\n[application]\nrun/main_scene="res://main.tscn"\nconfig/icon="res://art/icon.png"\n'
        '[autoload]\nGame="*res://game.gd"\n[internationalization]\n'
        'locale/translations=PackedStringArray("res://i18n/s.en.translation")\n')
    (tmp_path / "main.tscn").write_text('[gd_scene format=3]\n[ext_resource type="Theme" path="res://ui/theme.tres" id="1"]\n'
                                        '[node name="M" type="Node"]\n')
    (tmp_path / "ui" / "theme.tres").write_text('[gd_resource type="Theme" format=3]\n'
                                                '[ext_resource type="FontFile" path="res://ui/f.fnt" id="1"]\n[resource]\n')
    (tmp_path / "ui" / "f.fnt").write_text('info face="x" size=11\ncommon lineHeight=13 base=10 scaleW=64 scaleH=64 pages=1\n'
                                           'page id=0 file="f.png"\nchars count=0\n')
    for p in ("art/icon.png", "ui/f.png", "art/orphan.png"):
        Image.new("RGBA", (2, 2)).save(tmp_path / p)
    (tmp_path / "game.gd").write_text("extends Node\n")
    (tmp_path / "i18n" / "s.en.translation").write_bytes(b"RSRC")
    rep = tmp_path.parent / "unused.json"
    asset_unused.main([str(tmp_path), "--json", str(rep)])
    unused = json.loads(rep.read_text())["unused"]
    # 2.4.0 listed project.godot, the icon, the translation and the font page as unused
    assert unused == ["art/orphan.png"], unused


# ------------------------------------------------ bug 5: nav-to-godot islands at T-junctions
def test_nav_to_godot_welds_t_junctions():
    rects = [(0, 0, 64, 16), (0, 16, 16, 48)]   # corridor below the left end of a wider room strip
    verts, polys, _ = nav_to_godot.weld_polygons(rects)
    a, b = polys
    edges = lambda p: {frozenset((p[i], p[(i + 1) % len(p)])) for i in range(len(p))}
    # 2.4.0 gave each rectangle its own 4 vertices: no shared edge, so Godot never linked them
    assert edges(a) & edges(b), (verts, polys)
    assert len(verts) == len(set(map(tuple, verts)))
    assert (16, 16) in [tuple(v) for v in verts] and len(a) == 5


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_nav_to_godot_t_junction_path_in_godot(tmp_path):
    proj = tmp_path / "p"; proj.mkdir()
    (proj / "project.godot").write_text("config_version=5\n[navigation]\nworld/map_use_async_iterations=false\n")
    nav_to_godot.write_scene(str(proj / "nav.tscn"), [(0, 0, 64, 16), (0, 16, 16, 48)])
    out = _run_godot_script(tmp_path, proj, 'extends SceneTree\nfunc _initialize():\n'
                            '\troot.add_child(load("res://nav.tscn").instantiate())\n'
                            '\tfor i in 4:\n\t\tawait physics_frame\n'
                            '\tvar m = root.get_world_2d().navigation_map\n'
                            '\tvar p = NavigationServer2D.map_get_path(m, Vector2(56, 8), Vector2(8, 40), true)\n'
                            '\tprint("PATH_END %s" % [p[p.size() - 1] if p.size() else Vector2(-1, -1)])\n\tquit()\n')
    assert "PATH_END (8.0, 40.0)" in out, out[-1500:]


# ------------------------------------------------ sample-topdown
def test_topdown_readme_maps_every_generated_asset():
    readme = open(os.path.join(GAME, "README.md"), encoding="utf-8").read()
    build = open(os.path.join(GAME, "build.sh")).read()
    used = set(re.findall(r"^\s*(?:for .*; do )?gst ([a-z0-9-]+)", build, re.M))
    assert len(used) >= 80, len(used)
    assert {"dungeon-gen", "tileset-gen", "map-auto-layer", "map-stamp", "palette-apply", "team-outline",
            "palette-swap", "sfx-mix", "wav-loud-apply", "loc-to-godot", "font-subset", "input-map-lint",
            "game-data-lint", "drop-sim", "nav-to-godot", "atlas-to-godot", "asset-unused"} <= used
    for tool in used:
        assert "`gst %s" % tool in readme, tool
    for sub in ("art", "levels", "ui", "audio", "data", "i18n"):
        for dp, _, fs in os.walk(os.path.join(GAME, "project", sub)):
            for f in fs:
                if f.endswith((".import", ".uid")):
                    continue
                pat = re.sub(r"floor[12]", "floorN", f)
                pat2 = re.sub(r"^(floor[12]|boss)", "LEVEL", f)
                assert f in readme or pat in readme or pat2 in readme, f
    assert "## Usage" in readme and "## Source and licence" in readme and "## Known gaps" in readme
    loc = open(os.path.join(GAME, "data", "loc.csv"), encoding="utf-8").read()
    for ch in "äöüßéèàçê":
        assert ch in loc, ch


def _copy_game(tmp_path):
    dst = tmp_path / "sample-topdown"
    shutil.copytree(GAME, dst, ignore=shutil.ignore_patterns(".godot", "work", "media", "*.uid", "__pycache__"))
    return dst


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN not set")
def test_topdown_imports_clean_and_autoplay_clears_run(tmp_path):
    proj = _copy_game(tmp_path) / "project"
    env = _isolate(tmp_path)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    assert not re.search(r"ERROR|SCRIPT ERROR", r.stdout), r.stdout[-2000:]
    outs = []
    for loc in ("en", "de"):
        r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--fixed-fps", "60", "--",
                            "--autoplay", "--locale=" + loc, "--save=user://t_%s.json" % loc], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=240)
        out = r.stdout
        assert r.returncode == 0, out[-2500:]
        assert not re.search(r"ERROR|still in use|leaked", out), out[-2500:]
        assert "de=Glutgruft|Schlüssel gefunden!" in out and "fr=Crypte des Braises|Clé trouvée !" in out
        for marker in ("INPUT_OK true actions=8 with_gamepad=8", "LEVEL floor2", "LEVEL boss", "SAVE_OK floor=3",
                       "LOAD_OK floor=3", "KILL bat", "KILL wizard", "BOSS_DEAD", "TOPDOWN_WIN", "TOPDOWN_DONE"):
            assert marker in out, (marker, out[-2500:])
        assert "NAV_OK points=0" not in out
        save = re.search(r"TOPDOWN_DONE .* save=(.+)", out).group(1).strip()
        data = json.load(open(save))
        assert data[0]["floor"] == 3 and data[0]["locale"] == loc
        outs.append([l for l in out.splitlines() if l.startswith(("KILL", "PICKUP", "FLOOR_CLEAR", "TOPDOWN_WIN"))])
    # the seeded run plays out identically whatever the UI language
    assert outs[0] == outs[1]


def _digest(root):
    h = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".import", ".uid")):
                continue
            p = os.path.join(dp, f)
            h[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return h


def test_topdown_build_is_reproducible(tmp_path):
    game = _copy_game(tmp_path)
    env = dict(os.environ, GST_ROOT=ROOT)
    if godot_bin():
        env["GODOT_BIN"] = godot_bin()
    r = subprocess.run(["bash", str(game / "build.sh")], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=420)
    assert r.returncode == 0, r.stdout[-3000:]
    for sub in ("art", "levels", "ui", "audio", "data") + (("i18n",) if godot_bin() else ()):
        want = _digest(os.path.join(GAME, "project", sub))
        got = _digest(str(game / "project" / sub))
        assert got == want, (sub, sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))[:10])


def test_bundle_skips_example_work_dirs(tmp_path):
    """gst bundle walked examples/<game>/work (build.sh scratch: movie AVI, raw WAVs); 2.5.0 skips it."""
    root = tmp_path / "kit"
    (root / "examples" / "demo" / "work" / "movie").mkdir(parents=True)
    (root / "examples" / "demo" / "work" / "movie" / "big.avi").write_bytes(b"x" * 64)
    (root / "examples" / "demo" / "build.sh").write_text("#!/bin/sh\n")
    (root / "tool" / "work").mkdir(parents=True)                    # a 'work' folder outside examples/ is kept
    (root / "tool" / "work" / "keep.txt").write_text("k")
    shutil.copy(os.path.join(ROOT, "gst"), root / "gst")
    (root / "VERSION").write_text("9.9.9\n")
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(root / "gst"), "bundle", "-o", str(out)], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=60)
    assert r.returncode == 0, r.stdout
    import tarfile
    names = tarfile.open(next(out.glob("*.tar.gz"))).getnames()
    assert any(n.endswith("examples/demo/build.sh") for n in names)
    assert any(n.endswith("tool/work/keep.txt") for n in names)
    assert not any("/examples/demo/work/" in n for n in names), names
