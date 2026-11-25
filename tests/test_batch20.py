"""Batch 20 tools."""
import csv, json, os, struct, zlib, base64

import numpy as np
import pytest
from PIL import Image

import map_layer_split, ldtk_to_tiled, obj_transform, anim_splice
import tmx_infinite_to_finite, sfx_pitch, sprite_trim, glb_merge
import audio_tidy, obj_to_glb, mesh_pivot_fix


HFLIP = 0x80000000
VFLIP = 0x40000000


def _map(data, width=4, height=2, extra_layers=None, tilesets=None, objects=None, infinite=False, chunks=None):
    layer = {"type": "tilelayer", "name": "g", "width": width, "height": height, "data": data}
    if chunks is not None:
        layer = {"type": "tilelayer", "name": "g", "chunks": chunks}
    layers = [layer]
    if extra_layers:
        layers.extend(extra_layers)
    if objects is not None:
        layers.append({"type": "objectgroup", "name": "objs", "objects": objects})
    return {"type": "map", "width": width, "height": height, "tilewidth": 16, "tileheight": 16,
            "infinite": infinite,
            "tilesets": tilesets or [{"name": "t", "firstgid": 1, "tilecount": 20, "image": "t.png"}],
            "layers": layers}


def test_map_layer_split(tmp_path):
    tilesets = [
        {"name": "ground", "firstgid": 1, "tilecount": 10},
        {"name": "deco", "firstgid": 20, "tilecount": 5},
    ]
    data = [1, 20 | HFLIP, 0, 11, 5, 24, 0, 2]
    json.dump(_map(data, tilesets=tilesets), open(tmp_path / "m.json", "w"))
    assert map_layer_split.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "s.json"),
                                 "--layer", "g", "--drop-source", "--pretty",
                                 "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "s.json"))
    rec = json.load(open(tmp_path / "r.json"))
    names = [l["name"] for l in out["layers"] if l.get("type") == "tilelayer"]
    assert names == ["ground", "deco", "unassigned"]
    g, d, u = (next(l for l in out["layers"] if l["name"] == n)["data"] for n in names)
    assert g[0] == 1 and g[4] == 5 and g[7] == 2 and g[1] == 0
    assert d[1] == (20 | HFLIP) and d[5] == 24
    assert u[3] == 11  # 11 is outside both ranges
    assert rec["unassigned"] == 1
    with pytest.raises(SystemExit, match="overwrite"):
        map_layer_split.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])


def test_ldtk_to_tiled(tmp_path):
    tiles = [
        {"px": [0, 0], "src": [0, 0], "f": 0, "t": 4},
        {"px": [32, 16], "src": [16, 0], "f": 1, "t": 7},  # flipX
    ]
    lay = [
        {"__identifier": "Walls", "__type": "IntGrid", "__cWid": 3, "__cHei": 2, "__gridSize": 16,
         "intGridCsv": [0, 1, 1, 0, 2, 0]},
        {"__identifier": "Deco", "__type": "Tiles", "__cWid": 3, "__cHei": 2, "__gridSize": 16,
         "__tilesetDefUid": 7, "gridTiles": tiles},
        {"__identifier": "Things", "__type": "Entities", "__cWid": 3, "__cHei": 2, "__gridSize": 16,
         "entityInstances": [{"__identifier": "Chest", "px": [16, 16], "width": 16, "height": 16,
                              "fieldInstances": [{"__identifier": "loot", "__value": "gold"}]}]},
    ]
    proj = {
        "defs": {"tilesets": [{
            "uid": 7, "identifier": "dungeon", "relPath": "dungeon.png",
            "tileGridSize": 16, "pxWid": 128, "pxHei": 64, "__cWid": 8, "__cHei": 4,
        }]},
        "levels": [{"identifier": "L0", "layerInstances": lay}],
    }
    json.dump(proj, open(tmp_path / "p.ldtk", "w"))
    assert ldtk_to_tiled.main([str(tmp_path / "p.ldtk"), "-o", str(tmp_path / "maps"),
                               "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    m = json.load(open(tmp_path / "maps" / "L0.json"))
    assert m["width"] == 3 and m["height"] == 2 and m["tilewidth"] == 16
    ts = m["tilesets"][0]
    assert ts["name"] == "dungeon" and ts["firstgid"] == 1 and ts["tilecount"] == 32
    walls = next(l for l in m["layers"] if l["name"] == "Walls")
    deco = next(l for l in m["layers"] if l["name"] == "Deco")
    ents = next(l for l in m["layers"] if l["name"] == "Things")
    assert walls["data"] == [0, 1, 1, 0, 2, 0]
    assert deco["data"][0] == 5  # t=4 + firstgid 1
    assert deco["data"][5] == (8 | HFLIP)
    assert ents["objects"][0]["name"] == "Chest"
    assert any(p["name"] == "loot" and p["value"] == "gold" for p in ents["objects"][0]["properties"])
    with pytest.raises(SystemExit, match="overwrite"):
        ldtk_to_tiled.main([str(tmp_path / "p.ldtk"), "-o", str(tmp_path / "p.ldtk")])


def test_obj_transform(tmp_path):
    obj = tmp_path / "a.obj"
    obj.write_text("mtllib a.mtl\nv 1 0 0\nv 0 1 0\nv 0 0 1\nvn 1 0 0\nusemtl wood\nf 1 2 3\n")
    assert obj_transform.main([str(obj), "-o", str(tmp_path / "s.obj"), "--scale", "2,3,4",
                               "--json", str(tmp_path / "r.json")]) == 0
    verts = []
    for line in (tmp_path / "s.obj").read_text().splitlines():
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
    assert verts[0] == [2, 0, 0] and verts[1] == [0, 3, 0] and verts[2] == [0, 0, 4]
    text = (tmp_path / "s.obj").read_text()
    assert "mtllib a.mtl" in text and "usemtl wood" in text
    # rotate 90 about z: (1,0,0) -> (0,1,0)
    assert obj_transform.main([str(obj), "-o", str(tmp_path / "r90.obj"), "--rotate", "90", "--axis", "z"]) == 0
    v0 = [float(x) for x in [l for l in (tmp_path / "r90.obj").read_text().splitlines() if l.startswith("v ")][0].split()[1:4]]
    assert v0[0] == pytest.approx(0) and v0[1] == pytest.approx(1) and v0[2] == pytest.approx(0)
    # flip x
    assert obj_transform.main([str(obj), "-o", str(tmp_path / "fx.obj"), "--flip", "x"]) == 0
    v0 = [float(x) for x in [l for l in (tmp_path / "fx.obj").read_text().splitlines() if l.startswith("v ")][0].split()[1:4]]
    assert v0 == [-1, 0, 0]
    with pytest.raises(SystemExit, match="overwrite"):
        obj_transform.main([str(obj), "-o", str(obj), "--scale", "2"])


def test_anim_splice(tmp_path):
    data = {"clips": {
        "walk": {"frames": ["a", "b", "c", "d", "e"], "loop": True, "fps": 10,
                 "durations_ms": [100, 200, 300, 400, 500]},
        "idle": {"frames": ["i0", "i1"], "loop": True, "durations_ms": [80, 90]},
    }}
    json.dump(data, open(tmp_path / "c.json", "w"))
    assert anim_splice.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "ex.json"),
                             "--clip", "walk", "--from", "1", "--to", "4", "--pretty"]) == 0
    ex = json.load(open(tmp_path / "ex.json"))
    assert ex["clips"]["walk"]["frames"] == ["b", "c", "d"]
    assert ex["clips"]["walk"]["durations_ms"] == [200, 300, 400]
    assert ex["clips"]["walk"]["duration"] == 0.9
    assert ex["clips"]["idle"]["frames"] == ["i0", "i1"]
    assert anim_splice.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "cat.json"),
                             "--concat", "walk,idle", "--name", "combo", "--only"]) == 0
    cat = json.load(open(tmp_path / "cat.json"))
    assert list(cat["clips"]) == ["combo"]
    assert cat["clips"]["combo"]["frames"] == ["a", "b", "c", "d", "e", "i0", "i1"]
    assert cat["clips"]["combo"]["durations_ms"][-1] == 90
    with pytest.raises(SystemExit, match="overwrite"):
        anim_splice.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "c.json"),
                          "--clip", "walk", "--from", "0", "--to", "1"])


def test_tmx_infinite_to_finite(tmp_path):
    chunks = [
        {"x": 2, "y": 1, "width": 2, "height": 2, "data": [1, 2, 0, 3 | HFLIP]},
        {"x": 4, "y": 2, "width": 2, "height": 1, "data": [0, 5]},
    ]
    objects = [{"id": 1, "name": "door", "x": 32, "y": 16, "width": 16, "height": 16}]
    json.dump(_map([0], width=1, height=1, infinite=True, chunks=chunks, objects=objects),
              open(tmp_path / "inf.json", "w"))
    assert tmx_infinite_to_finite.main([str(tmp_path / "inf.json"), "-o", str(tmp_path / "f.json"),
                                        "--margin", "0", "--shift-objects", "--pretty",
                                        "--json", str(tmp_path / "r.json")]) == 0
    m = json.load(open(tmp_path / "f.json"))
    rec = json.load(open(tmp_path / "r.json"))
    assert m["infinite"] is False
    # used cells: (2,1),(3,1),(3,2),(5,2) -> origin 2,1 size 4x2
    assert rec["origin"] == [2, 1] and m["width"] == 4 and m["height"] == 2
    g = next(l for l in m["layers"] if l["type"] == "tilelayer")
    assert "chunks" not in g
    # (2,1)->(0,0)=1, (3,1)->(1,0)=2, (3,2)->(1,1)=3|HFLIP, (5,2)->(3,1)=5
    assert g["data"][0] == 1 and g["data"][1] == 2
    assert g["data"][1 + 4] == (3 | HFLIP) and g["data"][3 + 4] == 5
    door = next(l for l in m["layers"] if l.get("type") == "objectgroup")["objects"][0]
    assert door["x"] == 32 - 2 * 16 and door["y"] == 16 - 1 * 16
    with pytest.raises(SystemExit, match="overwrite"):
        tmx_infinite_to_finite.main([str(tmp_path / "inf.json"), "-o", str(tmp_path / "inf.json")])


def test_sfx_pitch(tmp_path):
    sr = 22050
    n = 22050  # 1 second
    y = (np.sin(np.linspace(0, 2 * np.pi * 440, n)) * 0.4).astype(np.float64)
    audio_tidy.write_wav(str(tmp_path / "a.wav"), y, sr)
    assert sfx_pitch.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "up.wav"),
                           "--semitones", "12", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    x2, sr2 = audio_tidy.read_wav(str(tmp_path / "up.wav"))
    assert sr2 == sr
    assert rec["frames_out"] == pytest.approx(n / 2, rel=0.02)
    assert abs(x2.shape[0] - n / 2) <= 1
    # ratio 0.5 = down an octave, twice as long
    assert sfx_pitch.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "dn.wav"), "--ratio", "0.5"]) == 0
    x3, _ = audio_tidy.read_wav(str(tmp_path / "dn.wav"))
    assert abs(x3.shape[0] - n * 2) <= 1
    with pytest.raises(SystemExit, match="overwrite"):
        sfx_pitch.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "a.wav"), "--semitones", "1"])


def test_sprite_trim(tmp_path):
    src = tmp_path / "sprites"
    src.mkdir()
    im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    for y in range(2, 6):
        for x in range(3, 8):
            im.putpixel((x, y), (255, 0, 0, 255))
    im.save(src / "a.png")
    Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(src / "empty.png")
    assert sprite_trim.main([str(src), "-o", str(tmp_path / "out"),
                             "--json", str(tmp_path / "trim.json")]) == 0
    cropped = Image.open(tmp_path / "out" / "a.png")
    assert cropped.size == (5, 4)  # x 3..8, y 2..6
    assert cropped.getpixel((0, 0))[0] == 255
    rec = json.load(open(tmp_path / "trim.json"))
    assert rec["frames"]["a"]["spriteSourceSize"] == {"x": 3, "y": 2, "w": 5, "h": 4}
    assert rec["frames"]["a"]["sourceSize"] == {"w": 10, "h": 10}
    assert rec["frames"]["empty"]["empty"] is True
    # same-dir would overwrite
    with pytest.raises(SystemExit, match="overwrite"):
        sprite_trim.main([str(src / "a.png"), "-o", str(src)])


def test_glb_merge(tmp_path):
    def cube(path, offset):
        # tiny triangle OBJ, shifted
        open(path, "w").write(
            f"v {offset} 0 0\nv {offset+1} 0 0\nv {offset} 1 0\nf 1 2 3\n"
        )
    cube(tmp_path / "a.obj", 0)
    cube(tmp_path / "b.obj", 10)
    assert obj_to_glb.main([str(tmp_path / "a.obj"), str(tmp_path / "b.obj"),
                            "-o", str(tmp_path / "glb")]) == 0
    a = tmp_path / "glb" / "a.glb"
    b = tmp_path / "glb" / "b.glb"
    assert a.exists() and b.exists()
    assert glb_merge.main([str(a), str(b), "-o", str(tmp_path / "m.glb"),
                           "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["meshes"] == 2
    js, chunks, ver = mesh_pivot_fix.read_glb(str(tmp_path / "m.glb"))
    assert ver == 2 and chunks
    roots = js["scenes"][0]["nodes"]
    wrappers = [js["nodes"][i] for i in roots]
    assert {n.get("name") for n in wrappers} == {"a", "b"}
    assert all(n.get("children") for n in wrappers)
    with pytest.raises(SystemExit, match="overwrite"):
        glb_merge.main([str(a), str(b), "-o", str(a)])
