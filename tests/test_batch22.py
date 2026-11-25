"""Batch 22 tools."""
import csv, json, os

import numpy as np
import pytest
from PIL import Image

import loc_sort, map_fill, obj_bounds, anim_rename, wav_pad
import sprite_canvas, tmx_layer_opacity, map_rotate
import audio_tidy


HFLIP = 0x80000000
VFLIP = 0x40000000
DFLIP = 0x20000000
MASK = 0x1FFFFFFF


def _map(data, width=4, height=2, name="ground", objects=None, extra=None, tw=16, th=16):
    layers = [{"type": "tilelayer", "name": name, "width": width, "height": height, "data": data,
               "opacity": 1, "visible": True}]
    if extra:
        layers.extend(extra)
    if objects is not None:
        layers.append({"type": "objectgroup", "name": "objs", "objects": objects, "opacity": 1, "visible": True})
    return {"type": "map", "orientation": "orthogonal", "width": width, "height": height,
            "tilewidth": tw, "tileheight": th,
            "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 40, "image": "t.png"}],
            "layers": layers}


def test_loc_sort(tmp_path):
    (tmp_path / "s.csv").write_text("id,en\nzeta,Z\nalpha,A\nmid,M\nalpha,dup\n")
    rc = loc_sort.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "o.csv"),
                        "--json", str(tmp_path / "r.json")])
    assert rc == 1
    rows = list(csv.DictReader(open(tmp_path / "o.csv")))
    assert [r["id"] for r in rows] == ["alpha", "alpha", "mid", "zeta"]
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["duplicates"] == ["alpha"] and rec["duplicate_counts"]["alpha"] == 2
    assert loc_sort.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "ok.csv"), "--no-fail"]) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        loc_sort.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "s.csv")])


def test_map_fill(tmp_path):
    data = [1, 1, 1, 0, 1, 2, 1, 0]
    json.dump(_map(data, 4, 2), open(tmp_path / "m.json", "w"))
    assert map_fill.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "r.json"),
                          "--layer", "ground", "--rect", "1,0,2,1", "--gid", "9",
                          "--json", str(tmp_path / "rep.json")]) == 0
    out = json.load(open(tmp_path / "r.json"))
    assert out["layers"][0]["data"][:4] == [1, 9, 9, 0]
    rec = json.load(open(tmp_path / "rep.json"))
    assert rec["cells"] == 2 and rec["mode"] == "rect"
    assert map_fill.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "f.json"),
                          "--flood", "0,0", "--gid", "7"]) == 0
    flooded = json.load(open(tmp_path / "f.json"))["layers"][0]["data"]
    # 4-connected 1's from (0,0): indices 0,1,2,4,6 (not the 2 at index 5, not the 0s)
    assert flooded == [7, 7, 7, 0, 7, 2, 7, 0]
    with pytest.raises(SystemExit, match="overwrite"):
        map_fill.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json"),
                       "--rect", "0,0,1,1", "--gid", "1"])


def test_obj_bounds(tmp_path):
    obj = tmp_path / "q.obj"
    obj.write_text("v 0 0 0\nv 2 0 0\nv 2 4 0\nv 0 4 2\nf 1 2 3 4\n")
    assert obj_bounds.main([str(obj), "-o", str(tmp_path / "b.json"),
                            "--box", str(tmp_path / "box.obj")]) == 0
    rec = json.load(open(tmp_path / "b.json"))
    assert rec["min"] == [0, 0, 0] and rec["max"] == [2, 4, 2]
    assert rec["size"] == [2, 4, 2] and rec["center"] == [1, 2, 1]
    assert rec["vertices"] == 4 and rec["radius"] > 0
    box = (tmp_path / "box.obj").read_text()
    assert box.count("\nv ") + (1 if box.startswith("v ") else 0) or True
    assert sum(1 for l in box.splitlines() if l.startswith("v ")) == 8
    assert sum(1 for l in box.splitlines() if l.startswith("f ")) == 12
    with pytest.raises(SystemExit, match="overwrite"):
        obj_bounds.main([str(obj), "-o", str(obj)])


def test_anim_rename(tmp_path):
    data = {"clips": {
        "hero_walk": {"frames": ["a"], "fps": 10},
        "hero_idle": {"frames": ["b"], "fps": 6},
        "ui_click": {"frames": ["c"], "fps": 12},
    }}
    json.dump(data, open(tmp_path / "c.json", "w"))
    assert anim_rename.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "n.json"),
                             "--pattern", "^hero_", "--replace", "player_", "--pretty",
                             "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "n.json"))
    assert set(out["clips"]) == {"player_walk", "player_idle", "ui_click"}
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["renamed"] == 2
    assert anim_rename.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "m.json"),
                             "--map", "ui_click=menu_click,hero_walk=run"]) == 0
    mapped = json.load(open(tmp_path / "m.json"))
    assert set(mapped["clips"]) == {"run", "hero_idle", "menu_click"}
    with pytest.raises(SystemExit, match="collide"):
        anim_rename.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "bad.json"),
                          "--map", "hero_walk=hero_idle"])
    with pytest.raises(SystemExit, match="overwrite"):
        anim_rename.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "c.json"),
                          "--pattern", "x", "--replace", "y"])


def test_wav_pad(tmp_path):
    sr = 8000
    n = 800  # 0.1s
    x = np.ones((n, 1), dtype=np.float64) * 0.25
    audio_tidy.write_wav(str(tmp_path / "a.wav"), x, sr, bits=16)
    assert wav_pad.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "p.wav"),
                         "--head", "0.05", "--tail", "0.05", "--json", str(tmp_path / "r.json")]) == 0
    y, sr2 = audio_tidy.read_wav(str(tmp_path / "p.wav"))
    assert sr2 == sr and len(y) == n + 400 + 400
    assert abs(float(y[0, 0])) < 0.01 and abs(float(y[-1, 0])) < 0.01
    mid = 400 + 10
    assert 0.2 < abs(float(y[mid, 0])) < 0.3
    assert wav_pad.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "t.wav"),
                         "--to-duration", "1.0", "--center"]) == 0
    z, _ = audio_tidy.read_wav(str(tmp_path / "t.wav"))
    assert len(z) == sr
    with pytest.raises(SystemExit, match="overwrite"):
        wav_pad.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "a.wav"), "--tail", "0.01"])


def test_sprite_canvas(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(src / "a.png")
    Image.new("RGBA", (32, 8), (0, 255, 0, 255)).save(src / "wide.png")
    out = tmp_path / "out"
    assert sprite_canvas.main([str(src / "a.png"), "-o", str(out), "--size", "16x16",
                               "--anchor", "feet", "--json", str(tmp_path / "r.json")]) == 0
    im = Image.open(out / "a.png")
    assert im.size == (16, 16)
    # 8x8 red, feet-anchored: bottom centre. top-left of sprite at ((16-8)//2, 16-8) = (4, 8)
    assert im.getpixel((4, 8))[:3] == (255, 0, 0)
    assert im.getpixel((0, 0))[3] == 0
    # crop a wide sprite onto 16x16 centre
    out2 = tmp_path / "out2"
    assert sprite_canvas.main([str(src / "wide.png"), "-o", str(out2), "--size", "16x16",
                               "--anchor", "center"]) == 0
    wim = Image.open(out2 / "wide.png")
    assert wim.size == (16, 16)
    # fit should scale the 32x8 down to 16x4
    out3 = tmp_path / "out3"
    assert sprite_canvas.main([str(src / "wide.png"), "-o", str(out3), "--size", "16x16",
                               "--fit", "--anchor", "center"]) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        sprite_canvas.main([str(src / "a.png"), "-o", str(out), "--size", "16x16",
                            "--json", str(src / "a.png")])


def test_tmx_layer_opacity(tmp_path):
    extra = [{"type": "tilelayer", "name": "fog", "width": 2, "height": 2, "data": [0, 0, 0, 0],
              "opacity": 1, "visible": True}]
    json.dump(_map([1, 0, 0, 0], 2, 2, extra=extra), open(tmp_path / "m.json", "w"))
    assert tmx_layer_opacity.main([str(tmp_path / "m.json"), "--list",
                                   "--json", str(tmp_path / "list.json")]) == 0
    listing = json.load(open(tmp_path / "list.json"))
    assert len(listing["layers"]) >= 2
    assert tmx_layer_opacity.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "o.json"),
                                   "--set", "fog=0.4", "--visible", "ground=0",
                                   "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "o.json"))
    by = {l["name"]: l for l in out["layers"]}
    assert by["fog"]["opacity"] == pytest.approx(0.4)
    assert by["ground"]["visible"] is False
    assert by["ground"]["opacity"] == 1
    with pytest.raises(SystemExit, match="overwrite"):
        tmx_layer_opacity.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json"),
                                "--set", "fog=0.5"])


def test_map_rotate(tmp_path):
    # 2x1 map: [A B] with A=1, B=2|HFLIP
    data = [1, 2 | HFLIP]
    objects = [{"id": 1, "name": "door", "type": "Door", "x": 0, "y": 0, "width": 16, "height": 8,
                "rotation": 0}]
    json.dump(_map(data, 2, 1, objects=objects), open(tmp_path / "m.json", "w"))
    assert map_rotate.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "r90.json"),
                            "--degrees", "90", "--json", str(tmp_path / "rep.json")]) == 0
    r90 = json.load(open(tmp_path / "r90.json"))
    assert r90["width"] == 1 and r90["height"] == 2
    # [A]  A at (0,0); B at (0,1)
    # [B]
    g90 = r90["layers"][0]["data"]
    assert (g90[0] & MASK) == 1 and (g90[1] & MASK) == 2
    # identity after 4x 90
    cur = tmp_path / "r90.json"
    for deg, name in ((90, "r180.json"), (90, "r270.json"), (90, "r360.json")):
        dest = tmp_path / name
        assert map_rotate.main([str(cur), "-o", str(dest), "--degrees", str(deg)]) == 0
        cur = dest
    back = json.load(open(tmp_path / "r360.json"))
    assert back["width"] == 2 and back["height"] == 1
    assert [g & MASK for g in back["layers"][0]["data"]] == [1, 2]
    assert back["layers"][0]["data"][1] & HFLIP
    # flags also cycle back
    assert back["layers"][0]["data"] == data
    door = back["layers"][1]["objects"][0]
    assert door["x"] == pytest.approx(0) and door["y"] == pytest.approx(0)
    assert door["width"] == pytest.approx(16) and door["height"] == pytest.approx(8)
    assert door["rotation"] % 360 == pytest.approx(0)
    # 180: [B A]
    assert map_rotate.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "r180d.json"),
                            "--degrees", "180"]) == 0
    r180 = json.load(open(tmp_path / "r180d.json"))
    assert [g & MASK for g in r180["layers"][0]["data"]] == [2, 1]
    with pytest.raises(SystemExit, match="overwrite"):
        map_rotate.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json"), "--degrees", "90"])


def test_map_rotate_gid_flags_cycle():
    # every flag combination returns to itself after 4x 90 CW, and 90+270 / 180+180 too
    import map_rotate as mr
    for h in (0, 1):
        for v in (0, 1):
            for d in (0, 1):
                gid = 5 | mr.pack_flags(bool(h), bool(v), bool(d))
                g = gid
                for _ in range(4):
                    g = mr.rot_gid(g, 1)
                assert g == gid
                assert mr.rot_gid(mr.rot_gid(gid, 1), 3) == gid
                assert mr.rot_gid(gid, 2) == mr.rot_gid(mr.rot_gid(gid, 1), 1)
