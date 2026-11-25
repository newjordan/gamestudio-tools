"""Batch 18 tools."""
import csv, json, os, struct, zlib, base64

import numpy as np
import pytest
from PIL import Image

import audio_tidy, tile_replace, atlas_to_godot, wav_dc_remove, map_layer_rename
import prefab_index, obj_recenter, anim_reverse, loc_missing, mesh_pivot_fix


HFLIP = 0x80000000


def _map(data, objects=None, encoded=False):
    layer = {"type": "tilelayer", "name": "g", "width": 4, "height": 2, "data": data}
    if encoded:
        raw = struct.pack("<" + "I" * len(data), *data)
        layer["data"] = base64.b64encode(zlib.compress(raw)).decode()
        layer["encoding"] = "base64"
        layer["compression"] = "zlib"
    layers = [layer]
    if objects is not None:
        layers.append({"type": "objectgroup", "name": "objs", "objects": objects})
    return {"type": "map", "width": 4, "height": 2, "tilewidth": 16, "tileheight": 16,
            "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 10}],
            "layers": layers}


def test_tile_replace(tmp_path):
    data = [1, 2 | HFLIP, 0, 3, 1, 0, 4, 2]
    objects = [{"id": 1, "name": "chest", "gid": 3, "x": 0, "y": 0, "width": 16, "height": 16}]
    json.dump(_map(data, objects), open(tmp_path / "m.json", "w"))
    json.dump({"1": 9, "3": 7}, open(tmp_path / "remap.json", "w"))
    assert tile_replace.main([str(tmp_path / "m.json"), "--remap", str(tmp_path / "remap.json"),
                              "-o", str(tmp_path / "o.json"), "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "o.json"))
    rec = json.load(open(tmp_path / "r.json"))
    g = out["layers"][0]["data"]
    assert g[0] == 9 and g[4] == 9
    assert g[1] == (2 | HFLIP)            # unmapped, flags kept
    assert g[3] == 7 and out["layers"][1]["objects"][0]["gid"] == 7
    assert rec["cells_changed"] == 4      # two 1s, one 3, one object 3
    # encoded input + unmapped 0 + CSV table
    json.dump(_map(data, encoded=True), open(tmp_path / "e.json", "w"))
    (tmp_path / "remap.csv").write_text("from,to\n1,5\n2,6\n")
    assert tile_replace.main([str(tmp_path / "e.json"), "--remap", str(tmp_path / "remap.csv"),
                              "-o", str(tmp_path / "e2.json"), "--unmapped", "0"]) == 0
    g2 = json.load(open(tmp_path / "e2.json"))["layers"][0]["data"]
    assert g2[0] == 5 and g2[1] == (6 | HFLIP) and g2[3] == 0 and g2[6] == 0
    with pytest.raises(SystemExit):
        tile_replace.main([str(tmp_path / "m.json"), "--remap", str(tmp_path / "remap.json"),
                           "-o", str(tmp_path / "m.json")])


def test_atlas_to_godot(tmp_path):
    atlas = {
        "frames": {
            "walk_01.png": {"frame": {"x": 0, "y": 0, "w": 8, "h": 8}},
            "walk_02.png": {"frame": {"x": 8, "y": 0, "w": 8, "h": 8}},
            "idle_01.png": {"frame": {"x": 0, "y": 8, "w": 8, "h": 8}},
        },
        "meta": {"image": "hero.png", "size": {"w": 16, "h": 16}},
    }
    json.dump(atlas, open(tmp_path / "atlas.json", "w"))
    clips = {"clips": {
        "walk": {"frames": ["walk_01.png", "walk_02.png"], "fps": 10, "loop": True, "durations_ms": [100, 150]},
        "idle": {"frames": ["idle_01.png"], "fps": 6, "loop": True},
    }}
    json.dump(clips, open(tmp_path / "clips.json", "w"))
    assert atlas_to_godot.main([str(tmp_path / "atlas.json"), "-o", str(tmp_path / "hero.tres"),
                                "--clips", str(tmp_path / "clips.json"), "--res", "res://art/hero.png"]) == 0
    text = open(tmp_path / "hero.tres").read()
    assert '[gd_resource type="SpriteFrames"' in text
    assert 'path="res://art/hero.png"' in text
    assert 'region = Rect2(0, 0, 8, 8)' in text and 'region = Rect2(8, 0, 8, 8)' in text
    assert '&"walk"' in text and '&"idle"' in text and "AtlasTexture_" in text
    assert atlas_to_godot.main([str(tmp_path / "atlas.json"), "-o", str(tmp_path / "all.tres")]) == 0
    assert '&"default"' in open(tmp_path / "all.tres").read()
    assert atlas_to_godot.main([str(tmp_path / "atlas.json"), "-o", str(tmp_path / "pf.tres"), "--per-frame"]) == 0
    assert '&"walk_01"' in open(tmp_path / "pf.tres").read()
    with pytest.raises(SystemExit):
        atlas_to_godot.main([str(tmp_path / "atlas.json"), "-o", str(tmp_path / "atlas.json")])
    # rotated refused
    atlas["frames"]["walk_01.png"]["rotated"] = True
    json.dump(atlas, open(tmp_path / "rot.json", "w"))
    with pytest.raises(SystemExit, match="rotated"):
        atlas_to_godot.main([str(tmp_path / "rot.json"), "-o", str(tmp_path / "r.tres")])


def test_atlas_to_godot_rotated(tmp_path):
    # an 8x12 upright sprite packed 90° CW as a 12x8 region at (0,0)
    from PIL import Image
    upright = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
    for y in range(12):
        upright.putpixel((0, y), (255, 0, 0, 255))  # left edge red
        upright.putpixel((7, y), (0, 0, 255, 255))  # right edge blue
    packed = upright.transpose(Image.Transpose.ROTATE_270)  # 90° CW → 12x8
    assert packed.size == (12, 8)
    sheet = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    sheet.paste(packed, (0, 0))
    sheet.save(tmp_path / "hero.png")
    atlas = {"frames": {
        "walk_01.png": {"frame": {"x": 0, "y": 0, "w": 12, "h": 8}, "rotated": True},
    }, "meta": {"image": "hero.png", "size": {"w": 12, "h": 8}}}
    json.dump(atlas, open(tmp_path / "atlas.json", "w"))
    assert atlas_to_godot.main([str(tmp_path / "atlas.json"), "-o", str(tmp_path / "hero.tres"),
                                "--sheet", str(tmp_path / "hero.png"),
                                "--res", "res://art/hero.png",
                                "--rotated-res", "res://art"]) == 0
    text = open(tmp_path / "hero.tres").read()
    unrot = tmp_path / "walk_01_unrot.png"
    assert unrot.exists()
    im = Image.open(unrot)
    assert im.size == (8, 12)
    assert im.getpixel((0, 0))[:3] == (255, 0, 0)
    assert im.getpixel((7, 0))[:3] == (0, 0, 255)
    assert 'path="res://art/walk_01_unrot.png"' in text
    assert "AtlasTexture_" not in text  # only the rotated frame was used
    assert "&\"default\"" in text or '&"default"' in text


def test_wav_dc_remove(tmp_path):
    sr = 8000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    x = (0.2 * np.sin(2 * np.pi * 220 * t) + 0.3).reshape(-1, 1).astype(np.float64)
    audio_tidy.write_wav(str(tmp_path / "off.wav"), x, sr, bits=16)
    assert wav_dc_remove.main([str(tmp_path / "off.wav"), "-o", str(tmp_path / "out"),
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))[0]
    assert rec["dc_before"][0] > 0.2
    y, sr2 = audio_tidy.read_wav(str(tmp_path / "out" / "off.wav"))
    assert sr2 == sr and abs(float(y.mean())) < 0.01
    assert abs(rec["dc_after"][0]) < 0.01
    with pytest.raises(SystemExit, match="overwrite"):
        wav_dc_remove.main([str(tmp_path / "off.wav")])
    assert wav_dc_remove.main([str(tmp_path / "off.wav"), "--dry-run"]) == 0


def test_map_layer_rename(tmp_path):
    m = _map([1, 0, 0, 0, 0, 0, 0, 0], objects=[{"id": 1, "name": "Spn_door", "x": 0, "y": 0}])
    m["layers"][0]["name"] = "fg_ground"
    m["layers"].append({"type": "group", "name": "fg_group", "layers": [
        {"type": "tilelayer", "name": "fg_detail", "width": 4, "height": 2, "data": [0] * 8}
    ]})
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_layer_rename.main([str(tmp_path / "m.json"), "--pattern", r"^fg_", "--repl", "front_",
                                  "-o", str(tmp_path / "o.json"), "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "o.json"))
    names = [out["layers"][0]["name"], out["layers"][2]["name"], out["layers"][2]["layers"][0]["name"]]
    assert names == ["front_ground", "front_group", "front_detail"]
    assert out["layers"][1]["objects"][0]["name"] == "Spn_door"   # objects not targeted
    assert map_layer_rename.main([str(tmp_path / "m.json"), "--pattern", "Spn", "--repl", "Spawn",
                                  "--targets", "objects", "--dry-run"]) == 0
    with pytest.raises(SystemExit):
        map_layer_rename.main([str(tmp_path / "m.json"), "--pattern", "a", "--repl", "b", "-o", str(tmp_path / "m.json")])
    # objects + layers together
    assert map_layer_rename.main([str(tmp_path / "m.json"), "--pattern", "Spn", "--repl", "Spawn",
                                  "--targets", "layers,objects", "-o", str(tmp_path / "o2.json")]) == 0
    assert json.load(open(tmp_path / "o2.json"))["layers"][1]["objects"][0]["name"] == "Spawn_door"


def test_prefab_index(tmp_path):
    a = _map([1, 2, 0, 0, 0, 0, 0, 0], objects=[
        {"id": 1, "name": "door", "type": "Door", "x": 0, "y": 0},
        {"id": 2, "name": "npc", "class": "NPC", "x": 16, "y": 0},
    ])
    a["name"] = "room_a"
    a["properties"] = [{"name": "biome", "value": "cave"}]
    b = _map([0] * 8)
    b["width"] = 8; b["layers"][0]["width"] = 8; b["layers"][0]["data"] = [0] * 16
    (tmp_path / "prefabs").mkdir()
    json.dump(a, open(tmp_path / "prefabs" / "room_a.json", "w"))
    json.dump(b, open(tmp_path / "prefabs" / "room_b.json", "w"))
    (tmp_path / "prefabs" / "notes.json").write_text('{"not": "a map"}')
    assert prefab_index.main([str(tmp_path / "prefabs"), "-o", str(tmp_path / "idx.csv")]) == 0
    rows = list(csv.DictReader(open(tmp_path / "idx.csv")))
    assert len(rows) == 2
    ra = next(r for r in rows if r["name"] == "room_a")
    assert ra["width"] == "4" and "Door:1" in ra["object_types"] and "NPC:1" in ra["object_types"]
    assert "biome" in ra["properties"]
    assert prefab_index.main([str(tmp_path / "prefabs"), "-o", str(tmp_path / "idx.json")]) == 0
    js = json.load(open(tmp_path / "idx.json"))
    assert len(js) == 2 and js[0]["object_count"] + js[1]["object_count"] == 2


def test_obj_recenter(tmp_path):
    obj = """# comment
mtllib p.mtl
o Prop
v 10 4 0
v 14 4 0
v 14 8 0
v 10 8 0
usemtl wood
g body
s 1
f 1 2 3 4
"""
    (tmp_path / "p.obj").write_text(obj)
    assert obj_recenter.main([str(tmp_path / "p.obj"), "-o", str(tmp_path / "c.obj"),
                              "--mode", "center", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    # centre of (10,4,0)-(14,8,0) is (12,6,0)
    assert rec["shift"] == pytest.approx([-12, -6, 0], abs=1e-6)
    text = open(tmp_path / "c.obj").read()
    assert "mtllib p.mtl" in text and "usemtl wood" in text and "g body" in text and "# comment" in text
    verts = [[float(x) for x in l.split()[1:4]] for l in text.splitlines() if l.startswith("v ")]
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    assert pytest.approx(min(xs) + max(xs), abs=1e-6) == 0
    assert pytest.approx(min(ys) + max(ys), abs=1e-6) == 0
    assert obj_recenter.main([str(tmp_path / "p.obj"), "-o", str(tmp_path / "b.obj"), "--mode", "bottom"]) == 0
    bverts = [[float(x) for x in l.split()[1:4]] for l in open(tmp_path / "b.obj") if l.startswith("v ")]
    assert min(v[1] for v in bverts) == pytest.approx(0, abs=1e-6)
    with pytest.raises(SystemExit):
        obj_recenter.main([str(tmp_path / "p.obj"), "-o", str(tmp_path / "p.obj")])
    assert obj_recenter.main([str(tmp_path / "p.obj"), "-o", str(tmp_path / "x.obj"), "--report"]) == 0
    assert not (tmp_path / "x.obj").exists()


def test_anim_reverse(tmp_path):
    clips = {"clips": {
        "walk": {"frames": ["a", "b", "c"], "fps": 12, "loop": True, "durations_ms": [100, 50, 150], "duration": 0.3},
        "idle": {"frames": ["i1", "i2"], "fps": 6, "loop": True},
    }}
    json.dump(clips, open(tmp_path / "c.json", "w"))
    assert anim_reverse.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "r.json"), "--pretty",
                              "--json", str(tmp_path / "rep.json")]) == 0
    out = json.load(open(tmp_path / "r.json"))
    assert out["clips"]["walk"]["frames"] == ["c", "b", "a"]
    assert out["clips"]["walk"]["durations_ms"] == [150, 50, 100]
    assert out["clips"]["walk"]["duration"] == 0.3
    assert out["clips"]["walk"]["loop"] is True and out["clips"]["walk"]["fps"] == 12
    assert out["clips"]["idle"]["frames"] == ["i2", "i1"]
    # only walk
    assert anim_reverse.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "w.json"), "--clips", "walk"]) == 0
    only = json.load(open(tmp_path / "w.json"))
    assert only["clips"]["walk"]["frames"] == ["c", "b", "a"]
    assert only["clips"]["idle"]["frames"] == ["i1", "i2"]
    with pytest.raises(SystemExit):
        anim_reverse.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "c.json")])
    with pytest.raises(SystemExit, match="unknown clip"):
        anim_reverse.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "z.json"), "--clips", "nope"])


def test_loc_missing(tmp_path):
    (tmp_path / "s.csv").write_text(
        "id,en,fr,de,notes\n"
        "hello,Hello,Bonjour,Hallo,ok\n"
        "bye,Bye,,Tschüss,\n"
        "empty,,,,"          # empty source: skipped
        "\n",
        encoding="utf-8",
    )
    rc = loc_missing.main([str(tmp_path / "s.csv"), "--source", "en", "-o", str(tmp_path / "m.json"), "--format", "json"])
    assert rc == 1
    rep = json.load(open(tmp_path / "m.json"))
    assert rep["missing"] == 1 and rep["rows"][0]["key"] == "bye" and rep["rows"][0]["lang"] == "fr"
    assert loc_missing.main([str(tmp_path / "s.csv"), "--langs", "de", "--no-fail"]) == 0
    # all present
    (tmp_path / "ok.csv").write_text("id,en,fr\nhi,Hi,Salut\n")
    assert loc_missing.main([str(tmp_path / "ok.csv")]) == 0
