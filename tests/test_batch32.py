"""Batch 32 tools: self-contained tests (no samples/ dependency)."""
import json, os, shutil, subprocess

import pytest
from PIL import Image

import ase_to_godot, data_to_godot, font_to_godot, hitbox_to_godot
import map_objects_to_godot, nav_to_godot, nine_slice_to_godot, tile_colliders_to_godot
from test_batch31 import _png, write_ase, godot_bin, _isolate


def test_map_objects_to_godot(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 4, "height": 2, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "objectgroup", "name": "ents", "objects": [
            {"id": 1, "name": "spawn", "type": "player", "x": 4, "y": 8, "width": 0, "height": 0, "point": True,
             "properties": [{"name": "facing", "value": "left"}]},
            {"id": 2, "name": "chest", "type": "loot", "x": 16, "y": 0, "width": 16, "height": 8,
             "properties": {"gold": 5}},
            {"id": 3, "name": "blob", "x": 0, "y": 0, "width": 8, "height": 8, "ellipse": True},
        ]}],
    }))
    out = tmp_path / "objs.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["objects"] == 3 and rec["shapes"] == 2
    text = out.read_text()
    assert 'type="Marker2D"' in text and 'type="Area2D"' in text
    assert "RectangleShape2D" in text and "CircleShape2D" in text
    assert 'metadata/tiled_type = "player"' in text
    assert 'metadata/facing = "left"' in text
    assert "metadata/gold = 5" in text
    with pytest.raises(SystemExit):
        map_objects_to_godot.main([str(src), "-o", str(src)])


def test_hitbox_to_godot(tmp_path):
    src = tmp_path / "h.json"
    src.write_text(json.dumps({
        "frames": {
            "hero.png": {
                "w": 16, "h": 16, "empty": False,
                "aabb": {"x": 1, "y": 2, "w": 8, "h": 10},
                "circle": {"cx": 5, "cy": 7, "r": 4},
                "capsule": {"cx": 5, "cy": 7, "r": 3, "length": 4, "axis": "y"},
            }
        }
    }))
    out = tmp_path / "h.tscn"
    assert hitbox_to_godot.main([str(src), "-o", str(out), "--shape", "aabb"]) == 0
    text = out.read_text()
    assert "RectangleShape2D" in text and "size = Vector2(8, 10)" in text
    assert "position = Vector2(5, 7)" in text  # centre 1+4, 2+5
    assert hitbox_to_godot.main([str(src), "-o", str(tmp_path / "c.tscn"), "--shape", "capsule"]) == 0
    cap = (tmp_path / "c.tscn").read_text()
    assert "CapsuleShape2D" in cap and "height = 10" in cap
    with pytest.raises(SystemExit):
        hitbox_to_godot.main([str(src), "-o", str(src)])


def test_tile_colliders_to_godot(tmp_path):
    src = tmp_path / "c.json"
    src.write_text(json.dumps({"rects": [{"x": 0, "y": 0, "w": 16, "h": 8}, {"x": 16, "y": 8, "w": 8, "h": 8}]}))
    out = tmp_path / "c.tscn"
    assert tile_colliders_to_godot.main([str(src), "-o", str(out)]) == 0
    text = out.read_text()
    assert 'type="StaticBody2D"' in text
    assert "size = Vector2(16, 8)" in text
    assert "position = Vector2(8, 4)" in text
    with pytest.raises(SystemExit):
        tile_colliders_to_godot.main([str(src), "-o", str(src)])


def test_nav_to_godot(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 4, "height": 2, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "tilelayer", "name": "ground", "width": 4, "height": 2,
                    "data": [0, 0, 1, 1, 0, 0, 1, 1]}],
    }))
    out = tmp_path / "nav.tscn"
    assert nav_to_godot.main([str(src), "-o", str(out), "--solid-layer", "ground",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["rects"] == 1 and rec["walkable"] == 4
    text = out.read_text()
    assert "NavigationRegion2D" in text and "NavigationPolygon" in text
    assert "PackedVector2Array(0, 0, 16, 0, 16, 16, 0, 16)" in text
    with pytest.raises(SystemExit):
        nav_to_godot.main([str(src), "-o", str(src), "--solid-layer", "ground"])


def test_nine_slice_to_godot(tmp_path):
    img = tmp_path / "p.png"
    _png(img, (16, 16), (200, 100, 50, 255))
    out = tmp_path / "p.tres"
    assert nine_slice_to_godot.main([str(img), "-o", str(out), "--insets", "3,4,5,6",
                                     "--res", "res://ui/", "--json", str(tmp_path / "r.json")]) == 0
    text = out.read_text()
    assert 'type="StyleBoxTexture"' in text
    assert "texture_margin_left = 3.0" in text and "texture_margin_bottom = 6.0" in text
    assert 'path="res://ui/p.png"' in text
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["insets"] == [3.0, 4.0, 5.0, 6.0]
    with pytest.raises(SystemExit):
        nine_slice_to_godot.main([str(img), "-o", str(img), "--insets", "1,1,1,1"])


def test_font_to_godot(tmp_path):
    _png(tmp_path / "font.png", (16, 8), (255, 255, 255, 255))
    fnt = tmp_path / "font.fnt"
    fnt.write_text(
        'info face="Test" size=8\n'
        "common lineHeight=8 base=7 scaleW=16 scaleH=8 pages=1 packed=0\n"
        'page id=0 file="font.png"\n'
        "chars count=2\n"
        "char id=65 x=0 y=0 width=8 height=8 xoffset=0 yoffset=0 xadvance=8 page=0 chnl=15\n"
        "char id=66 x=8 y=0 width=8 height=8 xoffset=0 yoffset=0 xadvance=8 page=0 chnl=15\n"
    )
    out = tmp_path / "theme.tres"
    dest = tmp_path / "fonts"
    assert font_to_godot.main([str(fnt), "-o", str(out), "--copy-dir", str(dest),
                               "--res", "res://fonts/", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["chars"] == 2 and rec["size"] == 8
    text = out.read_text()
    assert 'type="Theme"' in text and 'path="res://fonts/font.fnt"' in text
    assert "default_font_size = 8" in text
    assert (dest / "font.fnt").is_file() and (dest / "font.png").is_file()
    with pytest.raises(SystemExit):
        font_to_godot.main([str(fnt), "-o", str(fnt)])


def test_ase_to_godot(tmp_path):
    w, h = 2, 2
    px = bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 0, 255])
    src = write_ase(tmp_path / "hero.ase", w, h, px, duration=80, tag={"name": "idle", "from": 0, "to": 0})
    out = tmp_path / "hero.tres"
    frames = tmp_path / "frames"
    assert ase_to_godot.main([str(src), "-o", str(out), "--frames-dir", str(frames),
                              "--res", "res://hero/", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["frames"] == 1 and rec["animations"] == 1 and rec["tags"] == ["idle"]
    assert (frames / "frame_0000.png").is_file()
    text = out.read_text()
    assert "SpriteFrames" in text and '&"idle"' in text
    assert 'path="res://hero/frame_0000.png"' in text
    with pytest.raises(SystemExit):
        ase_to_godot.main([str(src), "-o", str(src)])


def test_data_to_godot(tmp_path):
    src = tmp_path / "items.csv"
    src.write_text("id,atk,magic,name\nsword,3,false,Iron Sword\nwand,1,true,Oak Wand\n")
    out = tmp_path / "items.tres"
    assert data_to_godot.main([str(src), "-o", str(out), "--res", "res://data/",
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["rows"] == 2 and rec["columns"] == ["id", "atk", "magic", "name"]
    text = out.read_text()
    assert 'type="Resource"' in text and 'path="res://data/items.gd"' in text
    assert '"atk": 3' in text and '"magic": true' in text
    assert (tmp_path / "items.gd").read_text().startswith("extends Resource")
    with pytest.raises(SystemExit):
        data_to_godot.main([str(src), "-o", str(src)])


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_batch32_resources_load_in_godot(tmp_path):
    """Load a few batch-32 scenes/resources in official Godot 4.7.2."""
    proj = tmp_path / "proj"
    proj.mkdir()
    # objects
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 2, "height": 1, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "objectgroup", "name": "ents", "objects": [
            {"id": 1, "name": "spawn", "type": "player", "x": 4, "y": 8, "point": True, "width": 0, "height": 0},
            {"id": 2, "name": "block", "x": 8, "y": 0, "width": 16, "height": 8},
        ]}],
    }))
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "objs.tscn")]) == 0
    # nav
    nsrc = tmp_path / "n.json"
    nsrc.write_text(json.dumps({
        "type": "map", "width": 4, "height": 2, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "tilelayer", "name": "ground", "width": 4, "height": 2,
                    "data": [0, 0, 1, 1, 0, 0, 1, 1]}],
    }))
    assert nav_to_godot.main([str(nsrc), "-o", str(proj / "nav.tscn"), "--solid-layer", "ground"]) == 0
    # style
    _png(proj / "panel.png", (16, 16), (200, 100, 50, 255))
    assert nine_slice_to_godot.main([str(proj / "panel.png"), "-o", str(proj / "style.tres"),
                                     "--insets", "3,3,3,3", "--res", "res://panel.png"]) == 0
    # data
    csv = tmp_path / "items.csv"
    csv.write_text("id,atk\nsword,3\n")
    assert data_to_godot.main([str(csv), "-o", str(proj / "items.tres"),
                               "--script", str(proj / "items.gd"), "--res", "res://items.gd"]) == 0
    (proj / "project.godot").write_text(
        "config_version=5\n\n[application]\n\nconfig/name=\"gst-b32-verify\"\n"
    )
    (proj / "check.gd").write_text(
        "extends SceneTree\n"
        "func _init() -> void:\n"
        "	var objs: PackedScene = load(\"res://objs.tscn\")\n"
        "	var nav: PackedScene = load(\"res://nav.tscn\")\n"
        "	var style = load(\"res://style.tres\")\n"
        "	var data = load(\"res://items.tres\")\n"
        "	if objs == null or nav == null or style == null or data == null:\n"
        "		push_error(\"FAILED load\")\n"
        "		quit(1)\n"
        "		return\n"
        "	var root = objs.instantiate()\n"
        "	var spawn = root.get_node(\"ents/spawn\")\n"
        "	print(\"SPAWN type=\", spawn.get_class(), \" meta=\", spawn.get_meta(\"tiled_type\"))\n"
        "	var block = root.get_node(\"ents/block\")\n"
        "	print(\"BLOCK class=\", block.get_class(), \" shapes=\", block.get_child_count())\n"
        "	var nroot = nav.instantiate()\n"
        "	var poly: NavigationPolygon = nroot.navigation_polygon\n"
        "	print(\"NAV outlines=\", poly.get_outline_count(), \" verts=\", poly.get_vertices().size())\n"
        "	print(\"STYLE class=\", style.get_class(), \" left=\", style.texture_margin_left)\n"
        "	print(\"DATA rows=\", data.rows.size(), \" atk=\", data.rows[0][\"atk\"])\n"
        "	quit(0)\n"
    )
    env = _isolate(tmp_path)
    imp = subprocess.run(
        [godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=90, text=True,
    )
    assert imp.returncode == 0, imp.stdout
    r = subprocess.run(
        [godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=90, text=True,
    )
    out = r.stdout or ""
    assert r.returncode == 0, out
    assert "SPAWN type=Marker2D meta=player" in out
    assert "BLOCK class=Area2D shapes=1" in out
    assert "NAV outlines=1 verts=4" in out
    assert "STYLE class=StyleBoxTexture left=3.0" in out
    assert "DATA rows=1 atk=3" in out
