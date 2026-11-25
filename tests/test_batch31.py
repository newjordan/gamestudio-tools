"""Batch 31 tools: self-contained tests (no samples/ dependency)."""
import json, os, struct, subprocess, zlib

import pytest
from PIL import Image

import anim_to_godot, ase_decode, asset_unused, dialogue_lint
import godot_res_lint, loc_to_godot, map_to_godot, texture_budget


def _png(path, size=(8, 8), color=(255, 0, 0, 255)):
    Image.new("RGBA", size, color).save(path)
    return path


def write_ase(path, w, h, rgba, duration=100, layer_name="Layer 1", tag=None):
    """Minimal 32-bit, one-frame, one-layer, raw-cel Aseprite file."""
    def pstr(s):
        b = s.encode("utf-8")
        return struct.pack("<H", len(b)) + b

    assert len(rgba) == w * h * 4
    layer_payload = struct.pack("<HHHHHHB", 1, 0, 0, 0, 0, 0, 255) + b"\x00\x00\x00" + pstr(layer_name)
    layer_chunk = struct.pack("<IH", 6 + len(layer_payload), 0x2004) + layer_payload
    cel_payload = struct.pack("<HhhBH", 0, 0, 0, 255, 0) + b"\x00" * 7 + struct.pack("<HH", w, h) + rgba
    cel_chunk = struct.pack("<IH", 6 + len(cel_payload), 0x2005) + cel_payload
    chunks = layer_chunk + cel_chunk
    if tag:
        body = struct.pack("<H", 1) + b"\x00" * 8
        body += struct.pack("<HHBH", tag["from"], tag["to"], 0, 0)
        body += b"\x00" * 6 + b"\xff\x00\x00" + b"\x00" + pstr(tag["name"])
        chunks += struct.pack("<IH", 6 + len(body), 0x2018) + body
    nchunks = 3 if tag else 2
    frame = struct.pack("<IHHH2sI", 16 + len(chunks), 0xF1FA, nchunks, duration, b"\x00\x00", 0) + chunks
    header = bytearray(128)
    struct.pack_into("<IHHHHHIH", header, 0, 128 + len(frame), 0xA5E0, 1, w, h, 32, 1, duration)
    struct.pack_into("<H", header, 32, 256)
    path.write_bytes(bytes(header) + frame)
    return path


def test_loc_to_godot(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text("id,en,fr,notes\nui.hello,Hello,Bonjour,x\nui.bye,Bye,Salut,\nskip,,,\n")
    out = tmp_path / "godot.csv"
    assert loc_to_godot.main([str(src), "-o", str(out), "--langs", "en,fr",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["keys"] == 2 and rec["locales"] == ["en", "fr"]
    lines = out.read_text().splitlines()
    assert lines[0] == "keys,en,fr"
    assert "ui.hello,Hello,Bonjour" in lines
    assert "skip" not in out.read_text()
    with pytest.raises(SystemExit):
        loc_to_godot.main([str(src), "-o", str(src)])


def test_map_to_godot_encode_and_scene(tmp_path):
    # 4x2 map, 8x8 tiles, two-tile sheet
    sheet = tmp_path / "tiles.png"
    _png(sheet, (16, 8), (0, 128, 0, 255))
    src = tmp_path / "m.json"
    # gid 1 = first tile (0,0), gid 2 = second (1,0); one flipped gid
    data = [1, 2, 1, 0, 2, 1 | 0x80000000, 0, 1]
    src.write_text(json.dumps({
        "type": "map", "width": 4, "height": 2, "tilewidth": 8, "tileheight": 8,
        "tilesets": [{"firstgid": 1, "columns": 2, "tilewidth": 8, "tileheight": 8,
                      "image": "tiles.png", "imagewidth": 16, "imageheight": 8, "tilecount": 2}],
        "layers": [{"type": "tilelayer", "name": "ground", "width": 4, "height": 2, "data": data}],
    }))
    tscn = tmp_path / "m.tscn"
    tres = tmp_path / "m_tileset.tres"
    assert map_to_godot.main([str(src), "-o", str(tscn), "--write-tileset", str(tres),
                              "--cells-json", str(tmp_path / "cells.json"),
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["cells"] == 6 and rec["flipped_cells"] == 1
    assert "flip_h = true" in tres.read_text() and "0:0/1 = 1" in tres.read_text()
    flipped = [c for c in json.load(open(tmp_path / "cells.json"))["cells"] if c.get("flip_h")]
    assert flipped and flipped[0]["alt"] == 1
    cells = json.load(open(tmp_path / "cells.json"))["cells"]
    assert any(c["x"] == 1 and c["y"] == 0 and c["atlas_x"] == 1 for c in cells)
    text = tscn.read_text()
    assert 'type="TileMapLayer"' in text and "PackedByteArray(" in text
    assert "TileSetAtlasSource" in tres.read_text()
    # decode the packed bytes and compare to the encoder
    inner = text.split("PackedByteArray(", 1)[1].split(")", 1)[0]
    raw = bytes(int(x.strip()) for x in inner.split(",") if x.strip())
    assert raw[:2] == b"\x00\x00"  # format 0
    with pytest.raises(SystemExit):
        map_to_godot.main([str(src), "-o", str(src)])


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
    return env


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_map_to_godot_loads_in_godot(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _png(proj / "tiles.png", (16, 8), (0, 128, 0, 255))
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 2, "height": 1, "tilewidth": 8, "tileheight": 8,
        "tilesets": [{"firstgid": 1, "columns": 2, "tilewidth": 8, "tileheight": 8,
                      "image": str(proj / "tiles.png"), "imagewidth": 16, "imageheight": 8, "tilecount": 2}],
        "layers": [{"type": "tilelayer", "name": "ground", "width": 2, "height": 1, "data": [1, 2]}],
    }))
    tscn = proj / "map.tscn"
    tres = proj / "tileset.tres"
    assert map_to_godot.main([str(src), "-o", str(tscn), "--write-tileset", str(tres),
                              "--tileset", "res://tileset.tres", "--res", "res://"]) == 0
    (proj / "project.godot").write_text(
        "config_version=5\n\n[application]\n\nconfig/name=\"gst-map-verify\"\n"
    )
    script = proj / "check.gd"
    script.write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var ps: PackedScene = load("res://map.tscn")\n'
        '	if ps == null:\n'
        '		push_error("FAILED load")\n'
        '		quit(1)\n'
        '		return\n'
        '	var root = ps.instantiate()\n'
        '	var layer: TileMapLayer = root.get_node("ground")\n'
        '	var used = layer.get_used_cells()\n'
        '	print("CELLS ", used.size())\n'
        '	for c in used:\n'
        '		var srcid = layer.get_cell_source_id(c)\n'
        '		var at = layer.get_cell_atlas_coords(c)\n'
        '		print("CELL ", c.x, ",", c.y, " src=", srcid, " atlas=", at.x, ",", at.y)\n'
        '	quit(0)\n'
    )
    env = _isolate(tmp_path)
    r = subprocess.run(
        [godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True,
    )
    out = r.stdout or ""
    assert r.returncode == 0, out
    assert "CELLS 2" in out
    assert "CELL 0,0 src=0 atlas=0,0" in out
    assert "CELL 1,0 src=0 atlas=1,0" in out


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_map_to_godot_flips_load_in_godot(tmp_path):
    """Tiled H/V/diagonal flags become alternative tiles; official Godot 4.7.2 must report them."""
    proj = tmp_path / "proj"
    proj.mkdir()
    _png(proj / "tiles.png", (16, 8), (0, 128, 0, 255))
    src = tmp_path / "m.json"
    H, V, D = 0x80000000, 0x40000000, 0x20000000
    data = [1, 1 | H, 1 | V, 1 | D, 1 | H | V, 1 | H | D, 1 | V | D, 1 | H | V | D]
    src.write_text(json.dumps({
        "type": "map", "width": 8, "height": 1, "tilewidth": 8, "tileheight": 8,
        "tilesets": [{"firstgid": 1, "columns": 2, "tilewidth": 8, "tileheight": 8,
                      "image": str(proj / "tiles.png"), "imagewidth": 16, "imageheight": 8, "tilecount": 2}],
        "layers": [{"type": "tilelayer", "name": "ground", "width": 8, "height": 1, "data": data}],
    }))
    tscn = proj / "map.tscn"
    tres = proj / "tileset.tres"
    assert map_to_godot.main([str(src), "-o", str(tscn), "--write-tileset", str(tres),
                              "--tileset", "res://tileset.tres", "--res", "res://"]) == 0
    body = tres.read_text()
    assert "0:0/4/transpose = true" in body
    assert "0:0/7/flip_h = true" in body and "0:0/7/flip_v = true" in body
    (proj / "project.godot").write_text(
        "config_version=5\n\n[application]\n\nconfig/name=\"gst-map-flip-verify\"\n"
    )
    (proj / "check.gd").write_text(
        "extends SceneTree\n"
        "func _init() -> void:\n"
        "	var ps: PackedScene = load(\"res://map.tscn\")\n"
        "	if ps == null:\n"
        "		push_error(\"FAILED load\")\n"
        "		quit(1)\n"
        "		return\n"
        "	var root = ps.instantiate()\n"
        "	var layer: TileMapLayer = root.get_node(\"ground\")\n"
        "	for x in range(8):\n"
        "		var c = Vector2i(x, 0)\n"
        "		var srcid = layer.get_cell_source_id(c)\n"
        "		var at = layer.get_cell_atlas_coords(c)\n"
        "		var alt = layer.get_cell_alternative_tile(c)\n"
        "		var td: TileData = layer.get_cell_tile_data(c)\n"
        "		if td == null:\n"
        "			print(\"CELL \", x, \" MISSING\")\n"
        "			continue\n"
        "		print(\"CELL \", x, \" src=\", srcid, \" atlas=\", at.x, \",\", at.y,\n"
        "			\" alt=\", alt, \" flip_h=\", td.flip_h, \" flip_v=\", td.flip_v,\n"
        "			\" transpose=\", td.transpose)\n"
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
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True,
    )
    out = r.stdout or ""
    assert r.returncode == 0, out
    expect = [
        (0, 0, False, False, False),
        (1, 1, True, False, False),
        (2, 2, False, True, False),
        (3, 4, False, False, True),
        (4, 3, True, True, False),
        (5, 5, True, False, True),
        (6, 6, False, True, True),
        (7, 7, True, True, True),
    ]
    for x, alt, fh, fv, tr in expect:
        needle = "CELL %d src=0 atlas=0,0 alt=%d flip_h=%s flip_v=%s transpose=%s" % (
            x, alt, str(fh).lower(), str(fv).lower(), str(tr).lower())
        assert needle in out, out + "\nmissing " + needle


def test_loc_to_godot_translation_tres(tmp_path, monkeypatch):
    """Without Godot, --translation-dir writes loadable Translation .tres files."""
    monkeypatch.delenv("GODOT_BIN", raising=False)
    src = tmp_path / "s.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Salut\n")
    out = tmp_path / "strings.csv"
    dest = tmp_path / "i18n"
    assert loc_to_godot.main([str(src), "-o", str(out), "--langs", "en,fr",
                              "--translation-dir", str(dest),
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["translation_format"] == "tres"
    fr = dest / "strings.fr.tres"
    assert fr.is_file()
    text = fr.read_text()
    assert 'locale = "fr"' in text and '&"ui.hello"' in text and '&"Bonjour"' in text


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_loc_to_godot_translation_via_godot(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Salut\n")
    out = tmp_path / "strings.csv"
    dest = tmp_path / "i18n"
    dest.mkdir()
    assert loc_to_godot.main([str(src), "-o", str(out), "--langs", "en,fr",
                              "--translation-dir", str(dest),
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["translation_format"] == "translation"
    fr = dest / "strings.fr.translation"
    en = dest / "strings.en.translation"
    assert fr.is_file() and en.is_file()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "project.godot").write_text(
        "config_version=5\n\n[application]\n\nconfig/name=\"gst-tr-verify\"\n"
    )
    import shutil
    shutil.copy2(fr, proj / "strings.fr.translation")
    shutil.copy2(en, proj / "strings.en.translation")
    (proj / "check.gd").write_text(
        "extends SceneTree\n"
        "func _init() -> void:\n"
        "	var fr: Translation = load(\"res://strings.fr.translation\")\n"
        "	var en: Translation = load(\"res://strings.en.translation\")\n"
        "	if fr == null or en == null:\n"
        "		push_error(\"FAILED load\")\n"
        "		quit(1)\n"
        "		return\n"
        "	print(\"FR \", fr.locale, \" \", fr.get_message(\"ui.hello\"), \" \", fr.get_class())\n"
        "	print(\"EN \", en.locale, \" \", en.get_message(\"ui.hello\"))\n"
        "	quit(0)\n"
    )
    env = _isolate(tmp_path)
    r = subprocess.run(
        [godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True,
    )
    text = r.stdout or ""
    assert r.returncode == 0, text
    assert "FR fr Bonjour OptimizedTranslation" in text
    assert "EN en Hello" in text


def test_ase_decode(tmp_path):
    w, h = 2, 2
    px = bytes([
        255, 0, 0, 255,  0, 255, 0, 255,
        0, 0, 255, 255,  255, 255, 0, 255,
    ])
    src = write_ase(tmp_path / "hero.ase", w, h, px, duration=80,
                    tag={"name": "idle", "from": 0, "to": 0})
    out = tmp_path / "frames"
    assert ase_decode.main([str(src), "-o", str(out), "--json", str(tmp_path / "ase.json")]) == 0
    rec = json.load(open(tmp_path / "ase.json"))
    assert rec["width"] == 2 and rec["height"] == 2 and rec["frames"][0]["duration_ms"] == 80
    assert rec["tags"][0]["name"] == "idle" and rec["layers"][0]["name"] == "Layer 1"
    im = Image.open(out / "frame_0000.png")
    assert im.size == (2, 2) and im.getpixel((0, 0)) == (255, 0, 0, 255)
    assert im.getpixel((1, 1)) == (255, 255, 0, 255)
    with pytest.raises(SystemExit):
        ase_decode.main([str(src), "-o", str(src)])


def test_asset_unused(tmp_path):
    root = tmp_path / "assets"
    root.mkdir()
    _png(root / "used.png")
    _png(root / "orphan.png")
    (root / "atlas.json").write_text(json.dumps({
        "frames": {"a": {"frame": {"x": 0, "y": 0, "w": 8, "h": 8}}},
        "meta": {"image": "used.png", "size": {"w": 8, "h": 8}},
    }))
    assert asset_unused.main([str(root), "--json", str(tmp_path / "u.json")]) == 0
    rec = json.load(open(tmp_path / "u.json"))
    assert rec["unused"] == ["orphan.png"]
    assert asset_unused.main([str(root), "--strict"]) == 1


def test_dialogue_lint(tmp_path):
    good = tmp_path / "ok.yarn"
    good.write_text(
        "title: Start\n---\nHello\n[[Next]]\n===\n"
        "title: Next\n---\nBye\n===\n"
    )
    assert dialogue_lint.main([str(good), "--json", str(tmp_path / "g.json")]) == 0
    bad = tmp_path / "bad.yarn"
    bad.write_text("title: Start\n---\nHello\n[[Missing]]\n===\n")
    assert dialogue_lint.main([str(bad), "--json", str(tmp_path / "b.json")]) == 1
    rec = json.load(open(tmp_path / "b.json"))
    assert rec["errors"] >= 1
    assert any("Missing" in f["msg"] for f in rec["findings"])
    ink = tmp_path / "q.ink"
    ink.write_text("== intro\nHello\n-> nowhere\n")
    assert dialogue_lint.main([str(ink)]) == 1


def test_godot_res_lint(tmp_path):
    proj = tmp_path / "game"
    art = proj / "art"
    art.mkdir(parents=True)
    _png(art / "hero.png")
    (proj / "main.tscn").write_text(
        '[gd_scene load_steps=2 format=3]\n\n'
        '[ext_resource type="Texture2D" path="res://art/hero.png" id="1"]\n'
        '[ext_resource type="Texture2D" path="res://art/missing.png" id="2"]\n'
    )
    (proj / "ok.gd").write_text('extends Node\n')
    assert godot_res_lint.main([str(proj), "--json", str(tmp_path / "r.json")]) == 1
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["errors"] and any("missing.png" in e["ref"] for e in rec["errors"])
    assert not any("hero.png" in e["ref"] and e.get("msg") == "missing" for e in rec["errors"])


def test_texture_budget(tmp_path):
    art = tmp_path / "art"
    art.mkdir()
    _png(art / "a.png", (8, 8))   # POT
    _png(art / "b.png", (10, 8))  # NPOT
    assert texture_budget.main([str(art), "--json", str(tmp_path / "r.json"), "--no-mips"]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["files"] == 2 and rec["npot"] == 1
    # 8*8*4 + 10*8*4 = 256 + 320 = 576
    assert rec["vram_bytes"] == 576
    assert texture_budget.main([str(art), "--no-mips", "--fail-over-mb", "0.0001"]) == 1


def test_anim_to_godot(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    _png(frames / "walk_1.png")
    _png(frames / "walk_2.png")
    clips = tmp_path / "clips.json"
    clips.write_text(json.dumps({
        "clips": {"walk": {"frames": ["walk_1", "walk_2"], "fps": 10, "loop": True}}
    }))
    out = tmp_path / "walk.tres"
    assert anim_to_godot.main([str(clips), "--frames", str(frames), "-o", str(out),
                               "--res", "res://frames/", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["textures"] == 2 and rec["animations"] == 1
    text = out.read_text()
    assert 'type="SpriteFrames"' in text
    assert "res://frames/walk_1.png" in text and '&"walk"' in text
    with pytest.raises(SystemExit):
        anim_to_godot.main([str(clips), "--frames", str(frames), "-o", str(clips)])
