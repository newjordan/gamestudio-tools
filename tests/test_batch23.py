"""Batch 23 tools: self-contained tests (no samples/ dependency)."""
import json, os, subprocess, sys

import numpy as np
import pytest
from PIL import Image

import anim_from_folder, glb_lod, glb_uv_transform, loc_key_lint, map_mirror, obj_merge, obj_to_glb
import sfx_reverse, tileset_merge, wav_loop_meta, wav_loop_snap, audio_tidy


def _wav(path, n=200, sr=8000, freq=440):
    t = np.linspace(0, n / sr, n, endpoint=False)
    x = (0.2 * np.sin(2 * np.pi * freq * t)).reshape(-1, 1).astype(np.float32)
    audio_tidy.write_wav(str(path), x, sr, bits=16)
    return x, sr


def test_sfx_reverse(tmp_path):
    src = tmp_path / "a.wav"
    x, sr = _wav(src, n=100)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 10, 40))
    x, sr = audio_tidy.read_wav(str(src))
    out = tmp_path / "rev.wav"
    assert sfx_reverse.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    y, sr2 = audio_tidy.read_wav(str(out))
    assert sr2 == sr
    assert np.allclose(y[:, 0], x[::-1, 0], atol=1e-4)
    loops = wav_loop_meta.read_loops(open(out, "rb").read())
    # original 10..40 inclusive; n=100; start' = 99-40=59, end'=99-10=89
    assert loops and loops[0]["start"] == 59 and loops[0]["end"] == 89
    # twice is identity
    out2 = tmp_path / "rev2.wav"
    assert sfx_reverse.main([str(out), "-o", str(out2)]) == 0
    z, _ = audio_tidy.read_wav(str(out2))
    assert np.allclose(z[:, 0], x[:, 0], atol=1e-4)
    loops2 = wav_loop_meta.read_loops(open(out2, "rb").read())
    assert loops2 and loops2[0]["start"] == 10 and loops2[0]["end"] == 40
    with pytest.raises(SystemExit, match="in-place"):
        sfx_reverse.main([str(src), "-o", str(src)])


def test_loc_key_lint(tmp_path):
    ok = tmp_path / "ok.csv"
    ok.write_text("id,en\nui.hello,Hello\nui.menu.start,Start\n")
    assert loc_key_lint.main([str(ok), "--prefix", "ui.", "--separator", ".",
                              "--json", str(tmp_path / "ok.json")]) == 0
    rec = json.load(open(tmp_path / "ok.json"))
    assert rec["issues"] == []
    bad = tmp_path / "bad.csv"
    bad.write_text("id,en\n"
                   "ui.hello,Hello\n"
                   "ui.hello,Dup\n"
                   "Bad Key!,x\n"
                   "ui..dot,x\n"
                   ".leading,x\n"
                   "no_prefix,x\n"
                   ",blank\n")
    rc = loc_key_lint.main([str(bad), "--prefix", "ui.", "--separator", ".",
                            "--json", str(tmp_path / "bad.json")])
    assert rc == 1
    msgs = " ".join(i["msg"] for i in json.load(open(tmp_path / "bad.json"))["issues"])
    assert "duplicate" in msgs and "charset" in msgs and "doubled" in msgs
    assert "prefix" in msgs and "blank" in msgs
    assert loc_key_lint.main([str(bad), "--prefix", "ui.", "--no-fail"]) == 0


def test_map_mirror(tmp_path):
    HFLIP, VFLIP, DFLIP = 0x80000000, 0x40000000, 0x20000000
    # 3x2: unique gids + one H-flipped and one D-flipped
    data = [
        1, 2 | HFLIP, 3,
        4 | DFLIP, 5, 6,
    ]
    m = {
        "type": "map", "width": 3, "height": 2, "tilewidth": 16, "tileheight": 16,
        "orientation": "orthogonal",
        "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 10}],
        "layers": [
            {"type": "tilelayer", "name": "g", "width": 3, "height": 2, "data": data},
            {"type": "objectgroup", "name": "objs", "objects": [
                {"id": 1, "x": 16, "y": 8, "width": 16, "height": 16},
                {"id": 2, "x": 8, "y": 8, "polygon": [{"x": 0, "y": 0}, {"x": 8, "y": 0}, {"x": 0, "y": 8}]},
                {"id": 3, "x": 0, "y": 16, "width": 16, "height": 16, "gid": 2 | HFLIP},
            ]},
        ],
    }
    src = tmp_path / "m.json"
    json.dump(m, open(src, "w"))
    out = tmp_path / "h.json"
    assert map_mirror.main([str(src), "-o", str(out), "--axis", "h", "--json", str(tmp_path / "r.json")]) == 0
    h = json.load(open(out))
    hd = h["layers"][0]["data"]
    # cells: (0,0)->(2,0), (1,0)->(1,0), (2,0)->(0,0)
    assert (hd[2] & 0x1FFFFFFF) == 1
    assert hd[2] & HFLIP  # 1 gained H
    assert (hd[1] & 0x1FFFFFFF) == 2
    assert not (hd[1] & HFLIP)  # 2 lost H
    assert (hd[0] & 0x1FFFFFFF) == 3
    assert hd[0] & HFLIP
    # D-flipped at (0,1) -> (2,1); D set so H-mirror toggles V
    cell = hd[1 * 3 + 2]
    assert (cell & 0x1FFFFFFF) == 4
    assert cell & DFLIP and cell & VFLIP
    objs = {o["id"]: o for o in h["layers"][1]["objects"]}
    assert objs[1]["x"] == pytest.approx(48 - 16 - 16)  # map_w=48
    assert objs[1]["y"] == 8
    # polygon origin flipped: (8,8) -> (48-8, 8)=(40,8)
    assert objs[2]["x"] == pytest.approx(40)
    # tile object gid flipped
    assert objs[3]["gid"] & 0x1FFFFFFF == 2
    assert not (objs[3]["gid"] & HFLIP)
    # 2x identity
    out2 = tmp_path / "h2.json"
    assert map_mirror.main([str(out), "-o", str(out2), "--axis", "h"]) == 0
    h2 = json.load(open(out2))
    assert h2["layers"][0]["data"] == data
    assert h2["layers"][1]["objects"][0]["x"] == 16
    # vertical + 2x
    v1 = tmp_path / "v.json"
    assert map_mirror.main([str(src), "-o", str(v1), "--axis", "v"]) == 0
    v2 = tmp_path / "v2.json"
    assert map_mirror.main([str(v1), "-o", str(v2), "--axis", "v"]) == 0
    assert json.load(open(v2))["layers"][0]["data"] == data
    with pytest.raises(SystemExit, match="in-place"):
        map_mirror.main([str(src), "-o", str(src), "--axis", "h"])


def test_obj_merge(tmp_path):
    a = tmp_path / "body.obj"
    b = tmp_path / "lid.obj"
    a.write_text("o body\ng body\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\n"
                 "f 1/1 2/2 3/3\n")
    b.write_text("o lid\ng lid\nv 0 2 0\nv 1 2 0\nv 0 3 0\nvt 0 1\nvt 1 1\nvt 0 0\n"
                 "f 1/1 2/2 3/3\n")
    out = tmp_path / "merged.obj"
    assert obj_merge.main([str(a), str(b), "-o", str(out), "--json", str(tmp_path / "j.json")]) == 0
    rec = json.load(open(tmp_path / "j.json"))
    assert rec["vertices"] == 6 and rec["faces"] == 2
    text = out.read_text()
    assert "g body" in text and "g lid" in text
    # remapped second face should refer to verts 4 5 6 and uvs 4 5 6
    assert "f 4/4 5/5 6/6" in text
    assert text.count("v ") == 6
    with pytest.raises(SystemExit, match="in-place"):
        obj_merge.main([str(a), str(b), "-o", str(a)])


def test_anim_from_folder(tmp_path):
    d = tmp_path / "frames"
    d.mkdir()
    for name in ("walk_01.png", "walk_02.png", "walk_03.png", "idle_01.png", "idle_02.png", "fx.png"):
        Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(d / name)
    out = tmp_path / "clips.json"
    assert anim_from_folder.main([str(d), "-o", str(out), "--pattern", "{clip}_{frame}.png",
                                  "--default-fps", "10", "--once", "idle",
                                  "--json", str(tmp_path / "r.json")]) == 0
    clips = json.load(open(out))["clips"]
    assert clips["walk"]["frames"] == ["walk_01", "walk_02", "walk_03"]
    assert clips["walk"]["fps"] == 10 and clips["walk"]["loop"] is True
    assert clips["idle"]["frames"] == ["idle_01", "idle_02"] and clips["idle"]["loop"] is False
    # leftover fx.png is unused
    rec = json.load(open(tmp_path / "r.json"))
    assert any("fx" in u for u in rec["unused"])
    # --clip glob
    out2 = tmp_path / "walk_only.json"
    assert anim_from_folder.main([str(d), "-o", str(out2), "--clip", "walk=walk_*.png",
                                  "--fps", "walk=8"]) == 0
    c2 = json.load(open(out2))["clips"]["walk"]
    assert c2["frames"] == ["walk_01", "walk_02", "walk_03"] and c2["fps"] == 8


def test_wav_loop_snap(tmp_path):
    src = tmp_path / "a.wav"
    x, sr = _wav(src, n=200)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 20, 69))
    out = tmp_path / "snap.wav"
    assert wav_loop_snap.main([str(src), "-o", str(out), "--json", str(tmp_path / "j.json")]) == 0
    y, _ = audio_tidy.read_wav(str(out))
    assert len(y) == 50  # 20..69 inclusive
    assert np.allclose(y[:, 0], x[20:70, 0], atol=1e-4)
    loops = wav_loop_meta.read_loops(open(out, "rb").read())
    assert loops and loops[0]["start"] == 0 and loops[0]["end"] == 49
    # pad past the end
    out2 = tmp_path / "pad.wav"
    assert wav_loop_snap.main([str(src), "-o", str(out2), "--start", "190", "--end", "209"]) == 0
    z, _ = audio_tidy.read_wav(str(out2))
    assert len(z) == 20
    assert np.allclose(z[:10, 0], x[190:200, 0], atol=1e-4)
    assert np.allclose(z[10:, 0], 0, atol=2 / 32768)
    with pytest.raises(SystemExit, match="in-place"):
        wav_loop_snap.main([str(src), "-o", str(src)])


def test_tileset_merge(tmp_path):
    a_img = tmp_path / "a.png"
    b_img = tmp_path / "b.png"
    # 2 tiles 8x8, 2 columns
    im_a = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    im_a.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (0, 0))
    im_a.paste(Image.new("RGBA", (8, 8), (0, 255, 0, 255)), (8, 0))
    im_a.save(a_img)
    im_b = Image.new("RGBA", (8, 8), (0, 0, 255, 255))
    im_b.save(b_img)
    tsa = {"name": "A", "tilewidth": 8, "tileheight": 8, "tilecount": 2, "columns": 2,
           "image": "a.png", "imagewidth": 16, "imageheight": 8,
           "tiles": [{"id": 1, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 100}]}]}
    tsb = {"name": "B", "tilewidth": 8, "tileheight": 8, "tilecount": 1, "columns": 1,
           "image": "b.png", "imagewidth": 8, "imageheight": 8}
    json.dump(tsa, open(tmp_path / "a.tsj", "w"))
    json.dump(tsb, open(tmp_path / "b.tsj", "w"))
    m = {
        "type": "map", "width": 2, "height": 1, "tilewidth": 8, "tileheight": 8,
        "tilesets": [
            {"firstgid": 1, "source": "a.tsj", "name": "A"},
            {"firstgid": 10, "source": "b.tsj", "name": "B"},
        ],
        "layers": [{"type": "tilelayer", "name": "g", "width": 2, "height": 1,
                    "data": [2, 10]}],
    }
    json.dump(m, open(tmp_path / "map.json", "w"))
    assert tileset_merge.main([
        str(tmp_path / "a.tsj"), str(tmp_path / "b.tsj"), "-o", str(tmp_path / "merged.tsj"),
        "--map", str(tmp_path / "map.json"), "--map-out", str(tmp_path / "map2.json"),
        "--json", str(tmp_path / "j.json"),
    ]) == 0
    merged = json.load(open(tmp_path / "merged.tsj"))
    assert merged["tilecount"] == 3 and merged["columns"] == 2
    assert (tmp_path / "merged.png").exists()
    sheet = Image.open(tmp_path / "merged.png")
    assert sheet.size[0] >= 16 and sheet.size[1] >= 8
    # B's tile (id 0) becomes local id 2; animation tileids on A unchanged (offset 0) / B +2
    anim = [t for t in merged["tiles"] if t["id"] == 1][0]["animation"]
    assert [f["tileid"] for f in anim] == [0, 1]
    m2 = json.load(open(tmp_path / "map2.json"))
    # A local 1 (gid 2) stays 1+1=2 if firstgid=1; B local 0 (gid 10) -> 1+2+0=3
    assert m2["layers"][0]["data"] == [2, 3]
    assert len(m2["tilesets"]) == 1
    with pytest.raises(SystemExit, match="in-place"):
        tileset_merge.main([str(tmp_path / "a.tsj"), str(tmp_path / "b.tsj"),
                            "-o", str(tmp_path / "a.tsj")])


def test_glb_uv_transform(tmp_path):
    obj = tmp_path / "quad.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "f 1/1 2/2 3/3\nf 1/1 3/3 4/4\n"
    )
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path / "glb")]) == 0
    src = next((tmp_path / "glb").glob("*.glb"))
    out = tmp_path / "uv.glb"
    assert glb_uv_transform.main([str(src), "-o", str(out), "--scale", "2,2", "--offset", "0.1,0",
                                  "--flip-u", "--json", str(tmp_path / "j.json")]) == 0
    js, bin_ = glb_lod.load_glb(str(out))
    prim = js["meshes"][0]["primitives"][0]
    uv = glb_lod.read_acc(js, bin_, prim["attributes"]["TEXCOORD_0"])
    js0, bin0 = glb_lod.load_glb(str(src))
    uv0 = glb_lod.read_acc(js0, bin0, js0["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"])
    want = uv0.astype(np.float64) * 2.0 + np.array([0.1, 0.0])
    want[:, 0] = 1.0 - want[:, 0]
    assert np.allclose(uv, want, atol=1e-5)
    with pytest.raises(SystemExit, match="in-place"):
        glb_uv_transform.main([str(src), "-o", str(src), "--flip-u"])
