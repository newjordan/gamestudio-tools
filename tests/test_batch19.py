"""Batch 19 tools."""
import csv, json, os, struct, zlib, base64, xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image, ImageChops

import atlas_pack, atlas_unpack
import map_layer_merge, loc_plurals, obj_triangulate, anim_pingpong
import tmx_embed_tileset, cubemap_pack, nav_grid


HFLIP = 0x80000000


def _sprite(path, color, size=8, margin=0):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(margin, size - margin):
        for x in range(margin, size - margin):
            im.putpixel((x, y), color)
    im.save(path)
    return path


def _map(data, width=4, height=2, extra_layers=None, tilesets=None, objects=None):
    layer = {"type": "tilelayer", "name": "g", "width": width, "height": height, "data": data}
    layers = [layer]
    if extra_layers:
        layers.extend(extra_layers)
    if objects is not None:
        layers.append({"type": "objectgroup", "name": "objs", "objects": objects})
    return {"type": "map", "width": width, "height": height, "tilewidth": 16, "tileheight": 16,
            "tilesets": tilesets or [{"name": "t", "firstgid": 1, "tilecount": 20, "image": "t.png"}],
            "layers": layers}


def test_atlas_unpack_roundtrip(tmp_path):
    src = tmp_path / "sprites"
    src.mkdir()
    a = _sprite(src / "walk_01.png", (255, 0, 0, 255), size=8, margin=1)
    b = _sprite(src / "walk_02.png", (0, 255, 0, 255), size=8, margin=2)
    work = tmp_path / "pack"
    work.mkdir()
    assert atlas_pack.main([str(src), "-o", str(work / "atlas"), "--padding", "1", "--no-pot"]) == 0
    raw = tmp_path / "raw"
    assert atlas_unpack.main([str(work / "atlas.json"), "-o", str(raw)]) == 0
    # cropped frames are trimmed (atlas-pack trims by default)
    r1 = Image.open(raw / "walk_01.png")
    assert r1.size == (6, 6) and r1.getpixel((0, 0))[0] == 255
    full = tmp_path / "full"
    assert atlas_unpack.main([str(work / "atlas.json"), "-o", str(full), "--untrim"]) == 0
    u1 = Image.open(full / "walk_01.png").convert("RGBA")
    o1 = Image.open(a).convert("RGBA")
    assert u1.size == o1.size
    assert u1.tobytes() == o1.tobytes()
    u2 = Image.open(full / "walk_02.png").convert("RGBA")
    o2 = Image.open(b).convert("RGBA")
    assert u2.tobytes() == o2.tobytes()
    # refuse dest == atlas image
    with pytest.raises(SystemExit, match="overwrite"):
        atlas_unpack.main([str(work / "atlas.json"), "-o", str(work / "atlas.png")])


def test_map_layer_merge(tmp_path):
    deco = {"type": "tilelayer", "name": "deco", "width": 4, "height": 2,
            "data": [0, 5 | HFLIP, 0, 0, 0, 0, 9, 0]}
    m = _map([1, 2, 0, 3, 1, 0, 4, 2], extra_layers=[deco])
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_layer_merge.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "o.json"),
                                 "--layers", "g,deco", "--name", "flat", "--drop-sources",
                                 "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "o.json"))
    rec = json.load(open(tmp_path / "r.json"))
    names = [l["name"] for l in out["layers"]]
    assert names == ["flat"]
    g = out["layers"][0]["data"]
    assert g[0] == 1 and g[1] == (5 | HFLIP) and g[6] == 9 and g[3] == 3
    assert rec["cells_overwritten"] == 2  # cell 1 (2->5|HFLIP) and cell 6 (4->9)
    # encoded input
    raw = struct.pack("<" + "I" * 8, * [1, 2, 0, 3, 1, 0, 4, 2])
    enc = {"type": "tilelayer", "name": "g", "width": 4, "height": 2,
           "encoding": "base64", "compression": "zlib",
           "data": base64.b64encode(zlib.compress(raw)).decode()}
    json.dump(_map([0]*8, extra_layers=[enc]) | {}, open(tmp_path / "e.json", "w"))
    # simpler: just put encoded as only layer
    em = _map([0]*8)
    em["layers"] = [enc, deco]
    json.dump(em, open(tmp_path / "e.json", "w"))
    assert map_layer_merge.main([str(tmp_path / "e.json"), "-o", str(tmp_path / "e2.json"),
                                 "--drop-sources"]) == 0
    g2 = json.load(open(tmp_path / "e2.json"))["layers"][0]["data"]
    assert g2[1] == (5 | HFLIP) and g2[0] == 1
    with pytest.raises(SystemExit, match="overwrite"):
        map_layer_merge.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])
    assert map_layer_merge.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json"),
                                 "--in-place"]) == 0


def test_loc_plurals(tmp_path):
    ok = tmp_path / "ok.csv"
    ok.write_text(
        "id,en,de,ja\n"
        "hello,Hello,Hallo,こんにちは\n"
        'items,"{n, plural, one {# item} other {# items}}",'
        '"{n, plural, one {# Objekt} other {# Objekte}}",'
        '"{n, plural, other {# 個}}"\n'
        "apples.one,1 apple,1 Apfel,りんご\n"
        "apples.other,{n} apples,{n} Äpfel,りんご\n"
    )
    assert loc_plurals.main([str(ok)]) == 0
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "id,en,pl\n"
        'items,"{n, plural, one {# item} other {# items}}","{n, plural, one {#} few {#}}"\n'
        "oranges.one,1 orange,1\n"
    )
    # pl items missing other + many; oranges family missing .other
    rc = loc_plurals.main([str(bad), "-o", str(tmp_path / "rep.json"), "--no-fail"])
    assert rc == 0
    rep = json.load(open(tmp_path / "rep.json"))
    kinds = {i["issue"] for i in rep["issues"]}
    assert "icu-missing-other" in kinds
    assert "suffix-missing-other" in kinds
    assert loc_plurals.main([str(bad)]) == 1
    with pytest.raises(SystemExit, match="overwrite"):
        loc_plurals.main([str(ok), "-o", str(ok)])


def test_obj_triangulate(tmp_path):
    obj = tmp_path / "q.obj"
    obj.write_text(
        "# comment\nmtllib q.mtl\n"
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "g body\nusemtl wood\ns 1\n"
        "f 1/1 2/2 3/3 4/4\n"
        "f 1/1 2/2 3/3\n"
    )
    assert obj_triangulate.main([str(obj), "-o", str(tmp_path / "t.obj"),
                                 "--json", str(tmp_path / "r.json")]) == 0
    text = (tmp_path / "t.obj").read_text()
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["ngons"] == 1 and rec["triangles_in"] == 1 and rec["triangles_out"] == 3
    assert "mtllib q.mtl" in text and "usemtl wood" in text and "g body" in text and "s 1" in text
    faces = [l for l in text.splitlines() if l.startswith("f ")]
    # ear-clip of a convex CCW quad starts at the first ear (vertex 0): (4,1,2)+(2,3,4)
    assert faces == ["f 4/4 1/1 2/2", "f 2/2 3/3 4/4", "f 1/1 2/2 3/3"]
    assert rec.get("fan_fallback", 0) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        obj_triangulate.main([str(obj), "-o", str(obj)])


def test_anim_pingpong(tmp_path):
    data = {"clips": {
        "walk": {"frames": ["a", "b", "c", "d"], "loop": True, "fps": 10,
                 "durations_ms": [100, 200, 300, 400]},
        "once": {"frames": ["a", "b", "c"], "loop": False, "duration": 0.3},
        "idle": {"frames": ["z"], "loop": True},
    }}
    json.dump(data, open(tmp_path / "c.json", "w"))
    assert anim_pingpong.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "p.json"),
                               "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "p.json"))
    assert out["clips"]["walk"]["frames"] == ["a", "b", "c", "d", "c", "b"]
    assert out["clips"]["walk"]["durations_ms"] == [100, 200, 300, 400, 300, 200]
    assert out["clips"]["walk"]["loop"] is True
    assert out["clips"]["walk"]["duration"] == 1.5
    assert out["clips"]["once"]["frames"] == ["a", "b", "c", "b", "a"]
    assert out["clips"]["idle"]["frames"] == ["z"]
    # only one clip
    assert anim_pingpong.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "w.json"),
                               "--clips", "walk"]) == 0
    w = json.load(open(tmp_path / "w.json"))
    assert w["clips"]["once"]["frames"] == ["a", "b", "c"]
    with pytest.raises(SystemExit, match="overwrite"):
        anim_pingpong.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "c.json")])


def test_tmx_embed_tileset(tmp_path):
    tsx = tmp_path / "dungeon.tsx"
    # minimal TSX
    ET.ElementTree(ET.fromstring(
        '<tileset name="dungeon" tilewidth="16" tileheight="16" tilecount="4" columns="2">'
        '<image source="dungeon.png" width="32" height="32"/>'
        '<tile id="0"><animation>'
        '<frame tileid="0" duration="100"/><frame tileid="1" duration="100"/>'
        "</animation></tile></tileset>"
    )).write(tsx)
    m = _map([1, 2, 0, 3, 1, 0, 4, 2],
             tilesets=[{"firstgid": 1, "source": "dungeon.tsx"}])
    json.dump(m, open(tmp_path / "level.json", "w"))
    assert tmx_embed_tileset.main([str(tmp_path / "level.json"), "-o", str(tmp_path / "emb.json"),
                                   "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "emb.json"))
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["embedded"] == 1
    ts = out["tilesets"][0]
    assert "source" not in ts
    assert ts["name"] == "dungeon" and ts["firstgid"] == 1 and ts["tilecount"] == 4
    assert ts["image"] == "dungeon.png"
    assert ts["tiles"][0]["animation"][0]["duration"] == 100
    with pytest.raises(SystemExit, match="overwrite"):
        tmx_embed_tileset.main([str(tmp_path / "level.json"), "-o", str(tmp_path / "level.json")])


def _face(path, color, size=4):
    Image.new("RGBA", (size, size), color).save(path)
    return path


def test_cubemap_pack_roundtrip(tmp_path):
    colors = {
        "px": (255, 0, 0, 255), "nx": (0, 255, 0, 255),
        "py": (0, 0, 255, 255), "ny": (255, 255, 0, 255),
        "pz": (255, 0, 255, 255), "nz": (0, 255, 255, 255),
    }
    args = []
    for n, c in colors.items():
        _face(tmp_path / f"{n}.png", c)
        args += [f"--{n}", str(tmp_path / f"{n}.png")]
    for layout in ("horizontal", "vertical", "cross"):
        out = tmp_path / f"{layout}.png"
        assert cubemap_pack.main(["pack", *args, "-o", str(out), "--layout", layout]) == 0
        dest = tmp_path / layout
        assert cubemap_pack.main(["unpack", str(out), "-o", str(dest)]) == 0
        for n, c in colors.items():
            im = Image.open(dest / f"{n}.png").convert("RGBA")
            assert im.size == (4, 4) and im.getpixel((0, 0)) == c
    # detect cross size
    im = Image.open(tmp_path / "cross.png")
    assert im.size == (16, 12)
    with pytest.raises(SystemExit, match="overwrite"):
        cubemap_pack.main(["pack", *args, "-o", str(tmp_path / "px.png")])


def test_nav_grid(tmp_path):
    # 4x3: solid ids 9 block a wall in the middle column of a ground-filled map
    # walkable everywhere except data==9
    data = [
        1, 1, 1, 1,
        1, 9, 9, 1,
        1, 1, 1, 1,
    ]
    objects = [{"id": 1, "name": "spawn", "x": 0, "y": 0, "width": 16, "height": 16}]
    json.dump(_map(data, width=4, height=3, objects=objects), open(tmp_path / "m.json", "w"))
    assert nav_grid.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "nav.png"),
                          "--solid-ids", "9", "--start", "0,0",
                          "--dist-csv", str(tmp_path / "d.csv"), "--scale", "4",
                          "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["walkable"] == 10  # 12-2
    assert rec["start"] == [0, 0]
    assert rec["reachable"] == 10
    rows = list(csv.reader(open(tmp_path / "d.csv")))
    dist = [list(map(int, r)) for r in rows]
    assert dist[0][0] == 0 and dist[1][1] == -1 and dist[1][2] == -1
    assert dist[0][3] == 3  # along the top
    assert dist[2][0] == 2
    im = Image.open(tmp_path / "nav.png")
    assert im.size == (16, 12)
    # start object used when --start omitted
    assert nav_grid.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "nav2.png"),
                          "--solid-ids", "9", "--scale", "1"]) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        nav_grid.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])
