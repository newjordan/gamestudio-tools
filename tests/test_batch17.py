"""Batch 17 tools."""
import json, os

import numpy as np
import pytest
from PIL import Image

import audio_tidy, map_crop, dialogue_to_ink, sprite_flip_sheet, tmx_props_lint
import contact_sheet, curve_trace, godot_tileset, wav_gap_squeeze, dialogue_extract, map_diff


def test_map_crop(tmp_path):
    m = {"type": "map", "width": 8, "height": 4, "tilewidth": 16, "tileheight": 16,
         "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4}],
         "layers": [
             {"type": "tilelayer", "name": "g", "width": 8, "height": 4,
              "data": [0]*8 + [0, 0, 5, 6, 0, 0, 0, 0] + [0]*16},
             {"type": "objectgroup", "name": "objs",
              "objects": [{"id": 1, "name": "door", "x": 32, "y": 16, "width": 16, "height": 16}]},
         ]}
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_crop.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "c.json"),
                          "--margin", "1", "--json", str(tmp_path / "r.json"), "--pretty"]) == 0
    out = json.load(open(tmp_path / "c.json"))
    rec = json.load(open(tmp_path / "r.json"))
    # used tiles at (2,1) and (3,1); margin 1 -> x=1..4, y=0..2
    assert out["width"] == rec["width"] and out["height"] == rec["height"]
    assert rec["x"] == 1 and rec["width"] == 4 and rec["height"] == 3
    # the two used tiles should still be neighbouring in the cropped data
    g = out["layers"][0]["data"]
    assert 5 in g and 6 in g and g.index(6) == g.index(5) + 1
    door = out["layers"][1]["objects"][0]
    assert door["x"] == 32 - rec["x"] * 16 and door["y"] == 16 - rec["y"] * 16
    with pytest.raises(SystemExit):
        map_crop.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])


def test_dialogue_to_ink(tmp_path):
    yarn = "title: Intro\n---\nAva: Hello. #line:l1\n-> Stay. #line:l2\n===\n"
    (tmp_path / "s.yarn").write_text(yarn)
    dialogue_extract.main([str(tmp_path / "s.yarn"), "-o", str(tmp_path / "d.csv")])
    json.dump({"Ava": "Captain"}, open(tmp_path / "map.json", "w"))
    assert dialogue_to_ink.main([str(tmp_path / "d.csv"), "-o", str(tmp_path / "s.ink"),
                                 "--speakers", str(tmp_path / "map.json")]) == 0
    text = open(tmp_path / "s.ink").read()
    assert "=== Intro ===" in text and "Captain: Hello. #line:l1" in text
    assert "* Stay. #line:l2" in text
    with pytest.raises(SystemExit):
        dialogue_to_ink.main([str(tmp_path / "d.csv"), "-o", str(tmp_path / "d.csv")])


def test_sprite_flip_sheet(tmp_path):
    sheet = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    # red on the left half
    for y in range(8):
        for x in range(4):
            sheet.putpixel((x, y), (255, 0, 0, 255))
    sheet.save(tmp_path / "s.png")
    atlas = {"frames": {"walk.png": {"frame": {"x": 0, "y": 0, "w": 8, "h": 8}}}, "meta": {"size": {"w": 8, "h": 8}}}
    json.dump(atlas, open(tmp_path / "s.json", "w"))
    assert sprite_flip_sheet.main([str(tmp_path / "s.png"), str(tmp_path / "s.json"),
                                   "-o", str(tmp_path / "f.png"), "--horizontal", "--pad", "1"]) == 0
    atl = json.load(open(tmp_path / "f.json"))
    assert "walk.png" in atl["frames"] and "walk_h.png" in atl["frames"]
    im = Image.open(tmp_path / "f.png")
    fr = atl["frames"]["walk_h.png"]["frame"]
    # flipped: red should now be on the right half of the frame
    px = im.getpixel((fr["x"] + 6, fr["y"] + 2))
    assert px[0] >= 250 and px[3] >= 250
    orig = atl["frames"]["walk.png"]["frame"]
    px0 = im.getpixel((orig["x"] + 1, orig["y"] + 2))
    assert px0[0] >= 250
    with pytest.raises(SystemExit):
        sprite_flip_sheet.main([str(tmp_path / "s.png"), str(tmp_path / "s.json"), "-o", str(tmp_path / "s.png")])


def test_tmx_props_lint(tmp_path):
    schema = {"objects": {
        "enemy": {"required": ["hp", "speed"], "types": {"hp": "int", "speed": "float", "elite": "bool"}},
        "*": {"required": ["name"]},
    }}
    json.dump(schema, open(tmp_path / "schema.json", "w"))
    m = {"type": "map", "width": 1, "height": 1, "tilewidth": 16, "tileheight": 16, "layers": [
        {"type": "objectgroup", "name": "mobs", "objects": [
            {"id": 1, "name": "gob", "type": "enemy",
             "properties": [{"name": "hp", "type": "int", "value": 10},
                            {"name": "speed", "type": "float", "value": 1.5},
                            {"name": "elite", "type": "bool", "value": False}]},
            {"id": 2, "name": "bad", "type": "enemy",
             "properties": [{"name": "hp", "type": "int", "value": "lots"}]},
            {"id": 3, "name": "", "type": "npc"},
        ]}
    ]}
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert tmx_props_lint.main([str(tmp_path / "m.json"), "--schema", str(tmp_path / "schema.json"),
                                "--json", str(tmp_path / "lint.json")]) == 1
    issues = json.load(open(tmp_path / "lint.json"))["issues"]
    kinds = {(i["object"], i["property"], i["kind"]) for i in issues}
    assert ("bad", "speed", "missing") in kinds and ("bad", "hp", "type") in kinds
    # unnamed npc trips the * required name
    assert any(i["object"] in (3, "?", "") and i["property"] == "name" and i["kind"] == "missing" for i in issues)
    # a clean map exits 0
    clean = {"type": "map", "layers": [{"type": "objectgroup", "name": "mobs", "objects": [
        {"id": 1, "name": "gob", "type": "enemy",
         "properties": [{"name": "hp", "type": "int", "value": 3}, {"name": "speed", "type": "float", "value": 1.0}]}
    ]}]}
    json.dump(clean, open(tmp_path / "ok.json", "w"))
    assert tmx_props_lint.main([str(tmp_path / "ok.json"), "--schema", str(tmp_path / "schema.json")]) == 0


def test_contact_sheet(tmp_path):
    d = tmp_path / "imgs"; d.mkdir()
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(d / "red.png")
    Image.new("RGBA", (32, 8), (0, 255, 0, 255)).save(d / "green.png")
    Image.new("RGBA", (8, 32), (0, 0, 255, 255)).save(d / "blue.png")
    assert contact_sheet.main([str(d), "-o", str(tmp_path / "c.png"), "--cell", "32x32",
                               "--columns", "2", "--pad", "4"]) == 0
    im = Image.open(tmp_path / "c.png")
    # 2 cols, 2 rows (3 images), cell 32 + caption 14 + pad 4
    assert im.width == 2 * 32 + 3 * 4
    assert im.height > 32 and im.getbbox() is not None
    with pytest.raises(SystemExit):
        contact_sheet.main([str(d / "red.png"), "-o", str(d / "red.png")])


def test_curve_trace(tmp_path):
    assert curve_trace.main(["--points", "0,0;4,2;8,0", "--count", "32",
                             "-o", str(tmp_path / "c.png"), "--gif", str(tmp_path / "c.gif"),
                             "--gif-frames", "8", "--width", "128", "--height", "96"]) == 0
    im = Image.open(tmp_path / "c.png")
    assert im.size == (128, 96) and im.getbbox() is not None
    g = Image.open(tmp_path / "c.gif")
    assert g.n_frames == 8


def test_godot_tileset(tmp_path):
    img = tmp_path / "tiles.png"
    Image.new("RGBA", (32, 16), (80, 140, 60, 255)).save(img)
    meta = {"tile": 16, "columns": 2, "count": 2, "image": str(img), "name": "grass"}
    json.dump(meta, open(tmp_path / "meta.json", "w"))
    assert godot_tileset.main([str(tmp_path / "meta.json"), "-o", str(tmp_path / "grass.tres"),
                               "--res", "res://art/tiles.png"]) == 0
    text = open(tmp_path / "grass.tres").read()
    assert '[gd_resource type="TileSet"' in text
    assert "res://art/tiles.png" in text
    assert "texture_region_size = Vector2i(16, 16)" in text
    assert "0:0/0 = 0" in text and "1:0/0 = 0" in text
    assert "sources/0 = SubResource" in text
    # from a raw image
    assert godot_tileset.main([str(img), "-o", str(tmp_path / "fromimg.tres"), "--tile", "16"]) == 0
    with pytest.raises(SystemExit):
        godot_tileset.main([str(img), "-o", str(img)])


def test_godot_tileset_collision_terrain_animation(tmp_path):
    # 3x1 tiles: 0 and 1 animate, 0 has a bottom-half box, wang edge bits on 0
    img = tmp_path / "tiles.png"
    Image.new("RGBA", (48, 16), (80, 140, 60, 255)).save(img)
    ts = {
        "name": "water", "tilewidth": 16, "tileheight": 16, "tilecount": 3, "columns": 3,
        "image": str(img),
        "tiles": [
            {"id": 0,
             "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 200}],
             "objectgroup": {"objects": [{"x": 0, "y": 8, "width": 16, "height": 8}]}},
            {"id": 2,
             "objectgroup": {"objects": [{"x": 0, "y": 0, "polygon": [
                 {"x": 8, "y": 0}, {"x": 16, "y": 16}, {"x": 0, "y": 16}]}]}},
        ],
        "wangsets": [{
            "name": "path", "type": "edge",
            "colors": [{"name": "dirt", "color": "#996633"}],
            "wangtiles": [
                {"tileid": 0, "wangid": [0, 0, 1, 0, 0, 0, 1, 0]},  # right + left
            ],
        }],
    }
    json.dump(ts, open(tmp_path / "water.tsj", "w"))
    assert godot_tileset.main([str(tmp_path / "water.tsj"), "-o", str(tmp_path / "water.tres"),
                               "--res", "res://art/tiles.png", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["animations"] == 1 and rec["collision_tiles"] == 2 and rec["terrain_sets"] == 1
    text = open(tmp_path / "water.tres").read()
    assert "0:0/animation_columns = 2" in text
    assert "0:0/animation_speed = 10" in text
    assert "0:0/animation_frame_0/duration = 1" in text
    assert "0:0/animation_frame_1/duration = 2" in text
    # tile 1 is reserved as an animation frame, not a standalone tile
    assert "1:0/0 = 0" not in text
    assert "2:0/0 = 0" in text
    # collision: tile 0 bottom half, center origin → y from 0 to 8
    assert "physics_layer_0/collision_layer = 1" in text
    assert "0:0/0/physics_layer_0/polygon_0/points = PackedVector2Array(" in text
    assert "-8, 0" in text and "8, 8" in text  # bottom-half box
    assert "2:0/0/physics_layer_0/polygon_0/points = PackedVector2Array(" in text
    assert 'terrain_set_0/mode = 2' in text
    assert 'terrain_set_0/terrain_0/name = "dirt"' in text
    assert "0:0/0/terrain_set = 0" in text
    assert "0:0/0/terrains_peering_bit/right_side = 0" in text
    assert "0:0/0/terrains_peering_bit/left_side = 0" in text
    # tile-colliders overlay on a 2-tile sheet
    Image.new("RGBA", (32, 16), (10, 10, 10, 255)).save(tmp_path / "ab.png")
    simple = {"name": "ab", "tilewidth": 16, "tileheight": 16, "tilecount": 2, "columns": 2,
              "image": str(tmp_path / "ab.png")}
    json.dump(simple, open(tmp_path / "ab.tsj", "w"))
    # one merged rect covering both tiles in sheet space
    json.dump({"tile": [16, 16], "rects": [{"x": 0, "y": 0, "w": 32, "h": 16}]},
              open(tmp_path / "col.json", "w"))
    assert godot_tileset.main([str(tmp_path / "ab.tsj"), "-o", str(tmp_path / "ab.tres"),
                               "--colliders", str(tmp_path / "col.json"),
                               "--json", str(tmp_path / "c.json")]) == 0
    assert json.load(open(tmp_path / "c.json"))["collision_tiles"] == 2
    ab = open(tmp_path / "ab.tres").read()
    assert "0:0/0/physics_layer_0/polygon_0/points" in ab
    assert "1:0/0/physics_layer_0/polygon_0/points" in ab


def test_godot_tileset_tsx(tmp_path):
    img = tmp_path / "t.png"
    Image.new("RGBA", (16, 16), (20, 20, 20, 255)).save(img)
    (tmp_path / "t.tsx").write_text(
        '<?xml version="1.0"?>\n'
        '<tileset name="t" tilewidth="16" tileheight="16" tilecount="1" columns="1">\n'
        f' <image source="{img.name}" width="16" height="16"/>\n'
        ' <tile id="0">\n'
        '  <objectgroup>\n'
        '   <object x="0" y="0" width="16" height="16"/>\n'
        '  </objectgroup>\n'
        ' </tile>\n'
        '</tileset>\n'
    )
    assert godot_tileset.main([str(tmp_path / "t.tsx"), "-o", str(tmp_path / "t.tres"),
                               "--res", "res://t.png"]) == 0
    assert "physics_layer_0/polygon_0/points" in open(tmp_path / "t.tres").read()


def test_wav_gap_squeeze(tmp_path):
    sr = 8000
    # 0.1s tone, 0.6s silence, 0.1s tone, 0.05s short silence, 0.1s tone
    def tone(n, amp=0.5, f=440):
        t = np.arange(n) / sr
        return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)[:, None]
    parts = [tone(int(0.1 * sr)), np.zeros((int(0.6 * sr), 1), np.float32),
             tone(int(0.1 * sr)), np.zeros((int(0.05 * sr), 1), np.float32), tone(int(0.1 * sr))]
    x = np.concatenate(parts, axis=0)
    audio_tidy.write_wav(str(tmp_path / "vo.wav"), x, sr)
    before = len(x) / sr
    assert wav_gap_squeeze.main([str(tmp_path / "vo.wav"), "--outdir", str(tmp_path / "out"),
                                 "--min-ms", "200", "--cap-ms", "80",
                                 "--json", str(tmp_path / "g.json")]) == 0
    rec = json.load(open(tmp_path / "g.json"))[0]
    assert rec["status"] == "squeezed" and rec["gaps"] == 1
    y, _ = audio_tidy.read_wav(str(tmp_path / "out" / "vo.wav"))
    # long 600ms gap became ~80ms; short 50ms gap kept; ~520ms saved
    assert rec["after_s"] < before - 0.4
    assert rec["squeezed_ms"] >= 400
    # leading/trailing not applicable (file starts and ends on tone)
    with pytest.raises(SystemExit):
        wav_gap_squeeze.main([str(tmp_path / "vo.wav")])
