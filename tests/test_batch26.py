"""Batch 26 tools: self-contained tests (no samples/ dependency)."""
import json, os

import numpy as np
import pytest
from PIL import Image

import audio_tidy, glb_lod, glb_weld, loc_rename, map_shift, obj_subdivide
import obj_to_glb, sprite_scale, tmx_world, wav_invert, wav_loop_meta, wav_mono


def _wav(path, x, sr=8000):
    audio_tidy.write_wav(str(path), np.asarray(x, dtype=np.float32), sr, bits=16)
    return path


def test_loc_rename(tmp_path):
    src = tmp_path / "a.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Au revoir\nkeep,K,G\n")
    out = tmp_path / "b.csv"
    assert loc_rename.main([str(src), "-o", str(out), "--map", "ui.hello=ui.hi,ui.bye=ui.farewell",
                            "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["renamed"] == 2
    rows = {r.split(",")[0]: r for r in out.read_text().splitlines()[1:]}
    assert "ui.hi" in rows and "ui.farewell" in rows and "keep" in rows
    assert "Hello" in rows["ui.hi"]
    # prefix
    out2 = tmp_path / "c.csv"
    assert loc_rename.main([str(src), "-o", str(out2), "--prefix", "game."]) == 0
    assert "game.ui.hello" in out2.read_text()
    # collision
    with pytest.raises(SystemExit, match="collision"):
        loc_rename.main([str(src), "-o", str(tmp_path / "x.csv"), "--map", "ui.hello=keep"])
    assert loc_rename.main([str(src), "-o", str(tmp_path / "pref.csv"), "--map", "ui.hello=keep",
                            "--prefer", "last"]) == 0
    # missing map key is ok unless --strict
    assert loc_rename.main([str(src), "-o", str(tmp_path / "m.csv"), "--map", "nope=x"]) == 0
    assert loc_rename.main([str(src), "-o", str(tmp_path / "s.csv"), "--map", "nope=x", "--strict"]) == 1
    with pytest.raises(SystemExit, match="in-place"):
        loc_rename.main([str(src), "-o", str(src), "--prefix", "x."])


def test_map_shift(tmp_path):
    m = {
        "type": "map", "width": 2, "height": 2, "tilewidth": 16, "tileheight": 16,
        "orientation": "orthogonal",
        "layers": [
            {"type": "tilelayer", "name": "g", "width": 2, "height": 2, "data": [1, 2, 3, 4]},
            {"type": "objectgroup", "name": "o", "objects": [
                {"id": 1, "x": 0, "y": 0, "width": 8, "height": 8},
            ]},
        ],
    }
    src = tmp_path / "m.json"
    json.dump(m, open(src, "w"))
    out = tmp_path / "s.json"
    assert map_shift.main([str(src), "-o", str(out), "--tiles", "1,0",
                           "--json", str(tmp_path / "r.json")]) == 0
    got = json.load(open(out))
    assert got["layers"][0]["data"] == [0, 1, 0, 3]
    assert got["layers"][1]["objects"][0]["x"] == 16
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["tiles_moved"] == 2
    wrap = tmp_path / "w.json"
    assert map_shift.main([str(src), "-o", str(wrap), "--tiles", "1,0", "--wrap"]) == 0
    assert json.load(open(wrap))["layers"][0]["data"] == [2, 1, 4, 3]
    # clip objects that leave
    clip = tmp_path / "c.json"
    assert map_shift.main([str(src), "-o", str(clip), "--tiles", "4,0", "--clip-objects"]) == 0
    assert json.load(open(clip))["layers"][1]["objects"] == []
    with pytest.raises(SystemExit, match="in-place"):
        map_shift.main([str(src), "-o", str(src), "--tiles", "1,0"])


def test_obj_subdivide(tmp_path):
    src = tmp_path / "t.obj"
    src.write_text("mtllib t.mtl\ng tri\nusemtl dirt\nv 0 0 0\nv 2 0 0\nv 0 2 0\nf 1 2 3\n")
    out = tmp_path / "s.obj"
    assert obj_subdivide.main([str(src), "-o", str(out), "--times", "1",
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["in_triangles"] == 1 and rec["out_triangles"] == 4
    text = out.read_text()
    assert "mtllib t.mtl" in text and "usemtl dirt" in text
    assert sum(1 for l in text.splitlines() if l.startswith("f ")) == 4
    out2 = tmp_path / "s2.obj"
    assert obj_subdivide.main([str(src), "-o", str(out2), "--times", "2"]) == 0
    assert sum(1 for l in out2.read_text().splitlines() if l.startswith("f ")) == 16
    ngon = tmp_path / "n.obj"
    ngon.write_text("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n")
    with pytest.raises(SystemExit, match="n-gon"):
        obj_subdivide.main([str(ngon), "-o", str(tmp_path / "x.obj")])
    with pytest.raises(SystemExit, match="in-place"):
        obj_subdivide.main([str(src), "-o", str(src)])


def test_wav_invert(tmp_path):
    n = 32
    x = (np.linspace(-0.4, 0.4, n).reshape(-1, 1)).astype(np.float32)
    src = _wav(tmp_path / "a.wav", x)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 4, 20))
    out = tmp_path / "b.wav"
    assert wav_invert.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    y, sr = audio_tidy.read_wav(str(out))
    src_x, _ = audio_tidy.read_wav(str(src))
    assert np.allclose(y, -src_x, atol=2 / 32767)
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 4 and loops[0]["end"] == 20
    with pytest.raises(SystemExit, match="in-place"):
        wav_invert.main([str(src), "-o", str(src)])


def test_sprite_scale(tmp_path):
    im = Image.new("RGBA", (2, 3), (0, 0, 0, 0))
    im.putpixel((0, 0), (255, 0, 0, 255))
    im.putpixel((1, 2), (0, 0, 255, 255))
    src = tmp_path / "a.png"
    im.save(src)
    out = tmp_path / "s.png"
    assert sprite_scale.main([str(src), "-o", str(out), "--scale", "2",
                              "--json", str(tmp_path / "r.json")]) == 0
    got = Image.open(out)
    assert got.size == (4, 6)
    assert got.getpixel((0, 0))[:3] == (255, 0, 0)
    assert got.getpixel((1, 1))[:3] == (255, 0, 0)
    assert got.getpixel((2, 4))[:3] == (0, 0, 255)
    out2 = tmp_path / "sz.png"
    assert sprite_scale.main([str(src), "-o", str(out2), "--size", "4x3"]) == 0
    assert Image.open(out2).size == (4, 3)
    with pytest.raises(SystemExit, match="in-place"):
        sprite_scale.main([str(src), "-o", str(src), "--scale", "2"])


def test_glb_weld(tmp_path):
    obj = tmp_path / "d.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "v 0 0 0\nv 1 1 0\n"
        "f 1 2 3\nf 5 6 4\n"
    )
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path)]) == 0
    src = tmp_path / "d.glb"
    assert src.exists()
    js, bin_ = glb_lod.load_glb(str(src))
    n_before = js["accessors"][js["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]["count"]
    assert n_before == 6
    out = tmp_path / "w.glb"
    assert glb_weld.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["vertices_after"] == 4 and rec["vertices_before"] == 6
    assert rec["triangles_after"] == 2
    with pytest.raises(SystemExit, match="obj-weld"):
        glb_weld.main([str(obj), "-o", str(tmp_path / "x.glb")])
    with pytest.raises(SystemExit, match="in-place"):
        glb_weld.main([str(src), "-o", str(src)])


def test_tmx_world(tmp_path):
    def mmap(name, cx, cy, data):
        m = {
            "type": "map", "width": 2, "height": 2, "tilewidth": 16, "tileheight": 16,
            "orientation": "orthogonal",
            "properties": [
                {"name": "chunk_x", "type": "int", "value": cx},
                {"name": "chunk_y", "type": "int", "value": cy},
            ],
            "layers": [{"type": "tilelayer", "name": "g", "width": 2, "height": 2, "data": data}],
        }
        p = tmp_path / name
        json.dump(m, open(p, "w"))
        return p
    a = mmap("chunk_0_0.json", 0, 0, [1, 2, 3, 4])
    b = mmap("chunk_2_0.json", 2, 0, [5, 6, 7, 8])
    world = tmp_path / "w.world"
    assert tmx_world.main([str(tmp_path), "-o", str(world), "--from-props",
                           "--json", str(tmp_path / "r.json")]) == 0
    w = json.load(open(world))
    assert w["type"] == "world" and len(w["maps"]) == 2
    by = {os.path.basename(m["fileName"]): m for m in w["maps"]}
    assert by["chunk_2_0.json"]["x"] == 32 and by["chunk_0_0.json"]["x"] == 0
    # grid layout of two nameless maps
    d = tmp_path / "grid"
    d.mkdir()
    for i, name in enumerate(("a.json", "b.json")):
        json.dump({"type": "map", "width": 2, "height": 1, "tilewidth": 8, "tileheight": 8,
                   "layers": [{"type": "tilelayer", "name": "g", "width": 2, "height": 1, "data": [1, 2]}]},
                  open(d / name, "w"))
    gworld = tmp_path / "g.world"
    assert tmx_world.main([str(d), "-o", str(gworld), "--layout", "grid", "--columns", "2"]) == 0
    gw = json.load(open(gworld))
    assert gw["maps"][1]["x"] == 16
    with pytest.raises(SystemExit, match="in-place"):
        tmx_world.main([str(a), "-o", str(a)])


def test_wav_mono(tmp_path):
    n = 16
    left = np.linspace(0.1, 0.3, n)
    right = np.linspace(-0.2, -0.4, n)
    x = np.stack([left, right], axis=1).astype(np.float32)
    src = _wav(tmp_path / "st.wav", x)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 2, 10))
    out = tmp_path / "m.wav"
    assert wav_mono.main([str(src), "-o", str(out), "--mode", "mix",
                          "--json", str(tmp_path / "r.json")]) == 0
    y, sr = audio_tidy.read_wav(str(out))
    src_x, _ = audio_tidy.read_wav(str(src))
    assert y.shape[1] == 1
    assert np.allclose(y.reshape(-1), src_x.mean(axis=1), atol=2 / 32767)
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 2 and loops[0]["end"] == 10
    left_out = tmp_path / "l.wav"
    assert wav_mono.main([str(src), "-o", str(left_out), "--mode", "left"]) == 0
    z, _ = audio_tidy.read_wav(str(left_out))
    assert np.allclose(z.reshape(-1), src_x[:, 0], atol=2 / 32767)
    with pytest.raises(SystemExit, match="in-place"):
        wav_mono.main([str(src), "-o", str(src)])
