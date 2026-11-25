"""Batch 16 tools, plus firstgid reindex, obj-weld material/group lines, and optional zstd hook."""
import base64, json, os, struct, sys, wave

import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from gst_errors import GstInputError
from PIL import Image

import audio_tidy, wav_chan_split, dialogue_to_yarn, tileset_wang, glb_rename_nodes, sheet_pad
import sfx_envelope, map_reorder, gif_optimize, map_clean, obj_weld, map_diff, tileset_gen, dialogue_extract


def test_wav_chan_split_and_join(tmp_path):
    sr = 16000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    stereo = np.stack([0.4 * np.sin(2 * np.pi * 440 * t), 0.2 * np.sin(2 * np.pi * 660 * t)], axis=1)
    src = tmp_path / "bus.wav"
    audio_tidy.write_wav(str(src), stereo, sr, bits=16)
    outdir = tmp_path / "stems"
    assert wav_chan_split.main([str(src), "-o", str(outdir), "--json", str(tmp_path / "s.json")]) == 0
    rec = json.load(open(tmp_path / "s.json"))[0]
    assert rec["channels"] == 2 and {s["name"] for s in rec["stems"]} == {"L", "R"}
    L, srL = audio_tidy.read_wav(str(outdir / "bus_L.wav"))
    R, _ = audio_tidy.read_wav(str(outdir / "bus_R.wav"))
    assert srL == sr and L.shape[1] == 1 and R.shape[1] == 1
    assert np.allclose(L[:, 0], stereo[:, 0], atol=2e-4) and np.allclose(R[:, 0], stereo[:, 1], atol=2e-4)
    joined = tmp_path / "back.wav"
    assert wav_chan_split.main([str(outdir / "bus_L.wav"), str(outdir / "bus_R.wav"), "--join", str(joined)]) == 0
    y, sr2 = audio_tidy.read_wav(str(joined))
    assert sr2 == sr and y.shape[1] == 2 and np.allclose(y, stereo, atol=3e-4)
    with pytest.raises(SystemExit):
        wav_chan_split.main([str(src)])  # no outdir/suffix
    with pytest.raises(SystemExit):
        wav_chan_split.main([str(outdir / "bus_L.wav"), str(outdir / "bus_R.wav"), "--join", str(outdir / "bus_L.wav")])


def test_dialogue_to_yarn(tmp_path):
    yarn = "title: Intro\n---\nAva: Hello there. #line:l1\n-> Stay. #line:l2\nBen: I will. #line:l3 #whisper\n===\n\ntitle: Outro\n---\nAva: Bye. #line:l4\n===\n"
    (tmp_path / "story.yarn").write_text(yarn)
    dialogue_extract.main([str(tmp_path / "story.yarn"), "-o", str(tmp_path / "d.csv")])
    json.dump({"Ava": "Captain"}, open(tmp_path / "map.json", "w"))
    assert dialogue_to_yarn.main([str(tmp_path / "d.csv"), "-o", str(tmp_path / "out.yarn"),
                                  "--speakers", str(tmp_path / "map.json")]) == 0
    text = open(tmp_path / "out.yarn").read()
    assert "title: Intro" in text and "title: Outro" in text
    assert "Captain: Hello there. #line:l1" in text
    assert "-> Stay. #line:l2" in text
    assert "Ben: I will. #line:l3" in text and "#whisper" in text
    with pytest.raises(SystemExit):
        dialogue_to_yarn.main([str(tmp_path / "d.csv"), "-o", str(tmp_path / "d.csv")])


def test_tileset_wang(tmp_path):
    # blob from tileset-gen meta (no image required)
    _sheet, meta = tileset_gen.build(t=8)
    json.dump(meta, open(tmp_path / "blob.json", "w"))
    assert tileset_wang.main([str(tmp_path / "blob.json"), "-o", str(tmp_path / "blob.tsj"),
                              "--image", "blob.png", "--pretty"]) == 0
    ts = json.load(open(tmp_path / "blob.tsj"))
    assert ts["tilecount"] == 47 and ts["columns"] == 8 and ts["wangsets"][0]["type"] == "mixed"
    tiles = ts["wangsets"][0]["wangtiles"]
    assert len(tiles) == 47 and tiles[0]["tileid"] == 0 and len(tiles[0]["wangid"]) == 8
    # full-neighbour mask should be all 1s on some tile
    assert any(t["wangid"] == [1] * 8 for t in tiles)
    # edge kind without input
    assert tileset_wang.main(["-o", str(tmp_path / "edge.tsj"), "--kind", "edge", "--image", "e.png"]) == 0
    et = json.load(open(tmp_path / "edge.tsj"))
    assert et["wangsets"][0]["type"] == "edge" and len(et["wangsets"][0]["wangtiles"]) == 16
    # mask 0 is empty wangid; mask 1 (N) has top edge
    by = {t["tileid"]: t["wangid"] for t in et["wangsets"][0]["wangtiles"]}
    assert by[0] == [0] * 8 and by[1][0] == 1 and by[1][2] == 0
    with pytest.raises(SystemExit):
        tileset_wang.main([str(tmp_path / "blob.json"), "-o", str(tmp_path / "blob.json")])


def test_glb_rename_nodes(tmp_path):
    gltf = {"asset": {"version": "2.0"},
            "nodes": [{"name": "Hero_Arm", "mesh": 0}, {"name": ""}],
            "meshes": [{"name": "Hero_Mesh"}],
            "materials": [{"name": "Hero_Mat"}],
            "skins": [{"name": "Hero_Skin", "joints": [0, 1], "skeleton": 0}],
            "scenes": [{"nodes": [0]}], "scene": 0}
    src = tmp_path / "hero.gltf"
    json.dump(gltf, open(src, "w"))
    assert glb_rename_nodes.main([str(src), "--pattern", "Hero", "--repl", "Boss", "--dry-run",
                                  "--targets", "nodes,meshes,materials,skins",
                                  "--json", str(tmp_path / "dry.json")]) == 0
    dry = json.load(open(tmp_path / "dry.json"))
    assert dry["changed"] >= 3 and not (tmp_path / "out.gltf").exists()
    assert glb_rename_nodes.main([str(src), "-o", str(tmp_path / "out.gltf"),
                                  "--pattern", "Hero", "--repl", "Boss",
                                  "--targets", "nodes,meshes,materials,skins"]) == 0
    out = json.load(open(tmp_path / "out.gltf"))
    assert out["nodes"][0]["name"] == "Boss_Arm" and out["meshes"][0]["name"] == "Boss_Mesh"
    assert out["materials"][0]["name"] == "Boss_Mat" and out["skins"][0]["name"] == "Boss_Skin"
    assert out["skins"][0]["joints"] == [0, 1]  # indices intact
    with pytest.raises(SystemExit):
        glb_rename_nodes.main([str(src), "-o", str(src)])


def test_sheet_pad(tmp_path):
    sheet = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    a = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    b = Image.new("RGBA", (8, 8), (0, 255, 0, 255))
    sheet.paste(a, (0, 0)); sheet.paste(b, (8, 0))
    sheet.save(tmp_path / "s.png")
    atlas = {"frames": {
        "red.png": {"frame": {"x": 0, "y": 0, "w": 8, "h": 8}, "rotated": False, "trimmed": False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": 8, "h": 8}, "sourceSize": {"w": 8, "h": 8}},
        "green.png": {"frame": {"x": 8, "y": 0, "w": 8, "h": 8}, "rotated": False, "trimmed": False,
                      "spriteSourceSize": {"x": 0, "y": 0, "w": 8, "h": 8}, "sourceSize": {"w": 8, "h": 8}},
    }, "meta": {"size": {"w": 16, "h": 8}, "image": "s.png"}}
    json.dump(atlas, open(tmp_path / "s.json", "w"))
    assert sheet_pad.main([str(tmp_path / "s.png"), str(tmp_path / "s.json"),
                           "-o", str(tmp_path / "p.png"), "--pad", "2"]) == 0
    out = Image.open(tmp_path / "p.png")
    atl = json.load(open(tmp_path / "p.json"))
    fr = atl["frames"]
    r, g = fr["red.png"]["frame"], fr["green.png"]["frame"]
    # 2px pad on every side; frames must not overlap and must still be 8x8
    assert r["w"] == 8 and g["w"] == 8
    assert abs((g["x"] - r["x"]) ) >= 8 + 2 or abs(g["y"] - r["y"]) >= 8 + 2
    px = out.getpixel((r["x"], r["y"]))
    assert px[0] >= 250 and px[3] >= 250
    # keep-layout also works
    assert sheet_pad.main([str(tmp_path / "s.png"), str(tmp_path / "s.json"),
                           "-o", str(tmp_path / "k.png"), "--atlas-out", str(tmp_path / "k.json"),
                           "--pad", "1", "--keep-layout"]) == 0
    with pytest.raises(SystemExit):
        sheet_pad.main([str(tmp_path / "s.png"), str(tmp_path / "s.json"), "-o", str(tmp_path / "s.png")])


def test_sfx_envelope(tmp_path):
    sr = 8000
    n = sr  # 1s of full-scale tone
    x = np.ones((n, 1), np.float32) * 0.8
    audio_tidy.write_wav(str(tmp_path / "tone.wav"), x, sr)
    assert sfx_envelope.main([str(tmp_path / "tone.wav"), "--outdir", str(tmp_path / "out"),
                              "--adsr", "100,100,0.5,200", "--json", str(tmp_path / "e.json")]) == 0
    rec = json.load(open(tmp_path / "e.json"))[0]
    assert rec["peak_before"] > 0.7 and rec["peak_after"] <= rec["peak_before"] + 1e-3
    y, _ = audio_tidy.read_wav(str(tmp_path / "out" / "tone.wav"))
    # start of attack near 0, sustain mid-clip near 0.8*0.5, end of release near 0
    assert abs(y[0, 0]) < 0.05
    mid = y[int(0.4 * sr), 0]
    assert 0.3 < abs(mid) < 0.5
    assert abs(y[-1, 0]) < 0.05
    with pytest.raises(SystemExit):
        sfx_envelope.main([str(tmp_path / "tone.wav")])


def test_map_reorder(tmp_path):
    m = {"type": "map", "width": 2, "height": 1, "tilewidth": 16, "tileheight": 16,
         "layers": [
             {"type": "tilelayer", "name": "ground", "width": 2, "height": 1, "data": [1, 2]},
             {"type": "objectgroup", "name": "mobs", "objects": [{"id": 1, "name": "b"}, {"id": 2, "name": "a"}]},
             {"type": "tilelayer", "name": "fg", "width": 2, "height": 1, "data": [3, 0]},
             {"type": "group", "name": "fx", "layers": [
                 {"type": "objectgroup", "name": "sparks", "objects": []},
                 {"type": "objectgroup", "name": "smoke", "objects": [{"id": 3, "name": "s"}]},
             ]},
         ]}
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_reorder.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "r.json"),
                             "--order", "fg,ground,fx/smoke,fx/sparks", "--objects", "mobs:a,b", "--pretty"]) == 0
    out = json.load(open(tmp_path / "r.json"))
    assert [l["name"] for l in out["layers"]][:2] == ["fg", "ground"]
    assert [o["name"] for o in out["layers"][list([i for i,l in enumerate(out["layers"]) if l["name"]=="mobs"])[0]]["objects"]] == ["a", "b"]
    fx = next(l for l in out["layers"] if l["name"] == "fx")
    assert [l["name"] for l in fx["layers"]] == ["smoke", "sparks"]
    with pytest.raises(SystemExit):
        map_reorder.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])


def test_gif_optimize(tmp_path):
    frames = []
    for i in range(6):
        im = Image.new("RGBA", (80, 40), (10, 20, 40, 255))
        # moving red square
        for y in range(8):
            for x in range(8):
                im.putpixel((8 + i * 8 + x, 10 + y), (255, 40, 40, 255))
        frames.append(im)
    frames[0].save(tmp_path / "big.gif", save_all=True, append_images=frames[1:], duration=80, loop=0)
    before = (tmp_path / "big.gif").stat().st_size
    assert gif_optimize.main([str(tmp_path / "big.gif"), "-o", str(tmp_path / "s.gif"),
                              "--colors", "16", "--scale", "0.5", "--json", str(tmp_path / "g.json")]) == 0
    rec = json.load(open(tmp_path / "g.json"))
    assert rec["frames"] == 6 and rec["size"] == [40, 20] and rec["bytes_after"] > 0
    out = Image.open(tmp_path / "s.gif")
    assert out.n_frames == 6 and out.size == (40, 20)
    with pytest.raises(SystemExit):
        gif_optimize.main([str(tmp_path / "big.gif"), "-o", str(tmp_path / "big.gif")])


def test_map_clean_reindex(tmp_path):
    # unused tileset at firstgid 1, used tileset at 20; flips and an object gid must remap
    FLIP = 0x80000000
    m = {"type": "map", "width": 3, "height": 1, "tilewidth": 16, "tileheight": 16,
         "tilesets": [{"name": "spare", "firstgid": 1, "tilecount": 10},
                      {"name": "used", "firstgid": 20, "tilecount": 5}],
         "layers": [
             {"type": "tilelayer", "name": "g", "width": 3, "height": 1, "data": [20, 21 | FLIP, 0]},
             {"type": "objectgroup", "name": "objs", "objects": [{"id": 1, "gid": 22, "x": 0, "y": 0}]},
         ]}
    c, r = map_clean.clean(m)
    assert [t["name"] for t in c["tilesets"]] == ["used"]
    assert c["tilesets"][0]["firstgid"] == 1
    assert r["firstgid_remap"] == {20: 1}
    assert c["layers"][0]["data"][0] == 1
    assert c["layers"][0]["data"][1] == (2 | FLIP)
    assert c["layers"][0]["data"][2] == 0
    assert c["layers"][1]["objects"][0]["gid"] == 3
    # --keep-firstgids leaves 20 in place
    c2, r2 = map_clean.clean(m, reindex=False)
    assert c2["tilesets"][0]["firstgid"] == 20 and c2["layers"][0]["data"][0] == 20 and r2["firstgid_remap"] == {}
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_clean.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "c.json")]) == 0
    out = json.load(open(tmp_path / "c.json"))
    assert out["tilesets"][0]["firstgid"] == 1 and out["layers"][0]["data"][0] == 1


def test_obj_weld_keeps_usemtl_and_groups(tmp_path):
    obj = """# comment
mtllib cube.mtl
v 0 0 0
v 1 0 0
v 0 1 0
v 0.0000004 0 0
g body
usemtl red
f 1 2 3
s off
usemtl blue
f 4 2 3
"""
    (tmp_path / "a.obj").write_text(obj)
    assert obj_weld.main([str(tmp_path / "a.obj"), "-o", str(tmp_path / "w.obj"), "--epsilon", "1e-5"]) == 0
    text = open(tmp_path / "w.obj").read()
    assert "mtllib cube.mtl" in text and "g body" in text
    assert "usemtl red" in text and "usemtl blue" in text and "s off" in text
    assert "# comment" in text
    assert sum(1 for l in text.splitlines() if l.startswith("v ")) == 3


def test_zstd_hook(tmp_path, monkeypatch):
    raw = struct.pack("<4I", 1, 2, 0, 3)
    class Fake:
        @staticmethod
        def decompress(b):
            assert b == b"FAKEZSTD"
            return raw
    # no decompressor -> clear error
    with pytest.raises(GstInputError) as ei:
        map_diff.decode_tile_data(base64.b64encode(b"FAKEZSTD").decode(), "base64", "zstd", "L")
    assert "zstd" in str(ei.value).lower()
    # hook: inject pyzstd
    monkeypatch.setitem(sys.modules, "pyzstd", Fake)
    out = map_diff.decode_tile_data(base64.b64encode(b"FAKEZSTD").decode(), "base64", "zstd", "L")
    assert out == [1, 2, 0, 3]
    monkeypatch.delitem(sys.modules, "pyzstd", raising=False)
