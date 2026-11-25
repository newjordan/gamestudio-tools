"""Batch 25 tools plus sfx-normalize --lufs: self-contained tests (no samples/ dependency)."""
import json, os, struct

import numpy as np
import pytest
from PIL import Image

import audio_tidy, glb_center, loc_diff, map_chunk, mesh_pivot_fix, obj_decimate
import sfx_normalize, sprite_rotate, tileset_renumber, tmx_decode, tmx_encode
import wav_batch_meta, wav_loop_meta, wav_resample


def _wav(path, x, sr=8000):
    audio_tidy.write_wav(str(path), np.asarray(x, dtype=np.float32), sr, bits=16)
    return path


def test_tmx_decode_roundtrip(tmp_path):
    m = {
        "type": "map", "width": 3, "height": 2, "tilewidth": 8, "tileheight": 8,
        "orientation": "orthogonal",
        "layers": [{"type": "tilelayer", "name": "g", "width": 3, "height": 2,
                    "data": [1, 2, 3, 4, 5, 0]}],
    }
    src = tmp_path / "m.json"
    json.dump(m, open(src, "w"))
    enc = tmp_path / "z.json"
    assert tmx_encode.main([str(src), "-o", str(enc), "--encoding", "base64", "--compression", "zlib"]) == 0
    z = json.load(open(enc))
    assert isinstance(z["layers"][0]["data"], str) and z["layers"][0]["encoding"] == "base64"
    out = tmp_path / "back.json"
    assert tmx_decode.main([str(enc), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    back = json.load(open(out))
    assert back["layers"][0]["data"] == [1, 2, 3, 4, 5, 0]
    assert "encoding" not in back["layers"][0]
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["encoding"] == "array" and rec["layers_or_chunks"] == 1
    csv_out = tmp_path / "c.json"
    assert tmx_decode.main([str(enc), "-o", str(csv_out), "--encoding", "csv"]) == 0
    c = json.load(open(csv_out))
    assert c["layers"][0]["encoding"] == "csv"
    assert map_diff_gids(c["layers"][0]) == [1, 2, 3, 4, 5, 0]
    with pytest.raises(SystemExit, match="in-place"):
        tmx_decode.main([str(enc), "-o", str(enc)])


def map_diff_gids(layer):
    import map_diff
    return map_diff.decode_tile_data(layer.get("data"), layer.get("encoding"), layer.get("compression"), "g")


def test_loc_diff(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Au revoir\nui.gone,Gone,Parti\n")
    b.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,BYE,Au revoir\nui.new,New,Nouveau\n")
    out = tmp_path / "d.csv"
    rc = loc_diff.main([str(a), str(b), "-o", str(out), "--json", str(tmp_path / "r.json")])
    assert rc == 1
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["only_in_a"] == ["ui.gone"] and rec["only_in_b"] == ["ui.new"]
    assert any(c["key"] == "ui.bye" for c in rec["changed"])
    text = out.read_text()
    assert "ui.gone,removed," in text and "ui.new,added," in text and "ui.bye,changed," in text
    assert loc_diff.main([str(a), str(b), "--no-fail"]) == 0
    same = tmp_path / "s.csv"
    a.write_text("id,en\nk,V\n")
    same.write_text("id,en\nk,V\n")
    assert loc_diff.main([str(a), str(same), "--json", str(tmp_path / "ok.json")]) == 0
    with pytest.raises(SystemExit, match="in-place"):
        loc_diff.main([str(a), str(b), "-o", str(a)])


def test_map_chunk(tmp_path):
    m = {
        "type": "map", "width": 4, "height": 2, "tilewidth": 16, "tileheight": 16,
        "orientation": "orthogonal",
        "layers": [
            {"type": "tilelayer", "name": "g", "width": 4, "height": 2,
             "data": [1, 2, 3, 4, 5, 6, 7, 8]},
            {"type": "objectgroup", "name": "o", "objects": [
                {"id": 1, "x": 8, "y": 0, "width": 16, "height": 8},
                {"id": 2, "x": 48, "y": 16, "width": 8, "height": 8},
            ]},
        ],
    }
    src = tmp_path / "m.json"
    json.dump(m, open(src, "w"))
    out = tmp_path / "chunks"
    world = tmp_path / "m.world"
    assert map_chunk.main([str(src), "-o", str(out), "--size", "2x2", "--world", str(world),
                           "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["chunks"] == 2
    a = json.load(open(out / "chunk_0_0.json"))
    b = json.load(open(out / "chunk_2_0.json"))
    assert a["width"] == 2 and a["layers"][0]["data"] == [1, 2, 5, 6]
    assert b["layers"][0]["data"] == [3, 4, 7, 8]
    # object 1 is in the first chunk (x=8); object 2 (x=48) in the second, shifted
    ids_a = [o["id"] for o in a["layers"][1]["objects"]]
    ids_b = [o["id"] for o in b["layers"][1]["objects"]]
    assert 1 in ids_a and 2 in ids_b
    obj2 = b["layers"][1]["objects"][0]
    assert obj2["x"] == 16  # 48 - 2*16
    w = json.load(open(world))
    assert w["type"] == "world" and len(w["maps"]) == 2
    assert w["maps"][1]["x"] == 32
    iso = dict(m, orientation="isometric")
    json.dump(iso, open(tmp_path / "iso.json", "w"))
    with pytest.raises(SystemExit, match="isometric"):
        map_chunk.main([str(tmp_path / "iso.json"), "-o", str(tmp_path / "x"), "--size", "2x2"])
    with pytest.raises(SystemExit, match="in-place"):
        map_chunk.main([str(src), "-o", str(src), "--size", "2x2"])


def test_obj_decimate(tmp_path):
    # 2x2 grid of quads as 8 triangles in the XY plane
    lines = ["mtllib grid.mtl", "g grid", "usemtl dirt"]
    # 3x3 verts
    for y in range(3):
        for x in range(3):
            lines.append(f"v {x} {y} 0")
    def vid(x, y):
        return y * 3 + x + 1
    for y in range(2):
        for x in range(2):
            a, b, c, d = vid(x, y), vid(x + 1, y), vid(x + 1, y + 1), vid(x, y + 1)
            lines.append(f"f {a} {b} {c}")
            lines.append(f"f {a} {c} {d}")
    src = tmp_path / "g.obj"
    src.write_text("\n".join(lines) + "\n")
    out = tmp_path / "g_lod.obj"
    # ratio 1 must keep 8 triangles (or very close); small ratio must drop some
    assert obj_decimate.main([str(src), "-o", str(tmp_path / "same.obj"), "--ratio", "1",
                              "--json", str(tmp_path / "r1.json")]) == 0
    r1 = json.load(open(tmp_path / "r1.json"))
    assert r1["in_triangles"] == 8 and r1["out_triangles"] == 8
    assert obj_decimate.main([str(src), "-o", str(out), "--ratio", "0.25",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["out_triangles"] < rec["in_triangles"]
    text = out.read_text()
    assert "mtllib grid.mtl" in text and "usemtl dirt" in text and "g grid" in text
    n_f = sum(1 for l in text.splitlines() if l.startswith("f "))
    assert n_f == rec["out_triangles"]
    ngon = tmp_path / "ngon.obj"
    ngon.write_text("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n")
    with pytest.raises(SystemExit, match="n-gon"):
        obj_decimate.main([str(ngon), "-o", str(tmp_path / "x.obj")])
    with pytest.raises(SystemExit, match="in-place"):
        obj_decimate.main([str(src), "-o", str(src), "--ratio", "0.5"])


def test_wav_resample(tmp_path):
    n, sr = 80, 8000
    t = np.linspace(0, n / sr, n, endpoint=False)
    x = (0.4 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1).astype(np.float32)
    src = _wav(tmp_path / "a.wav", x, sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 10, 40))
    out = tmp_path / "b.wav"
    assert wav_resample.main([str(src), "-o", str(out), "--rate", "16000",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))["files"][0]
    y, sr2 = audio_tidy.read_wav(str(out))
    assert sr2 == 16000 and rec["frames_out"] == 160
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 20 and loops[0]["end"] == 80
    # identity rate keeps length
    assert wav_resample.main([str(src), "-o", str(tmp_path / "same.wav"), "--rate", "8000"]) == 0
    z, sr3 = audio_tidy.read_wav(str(tmp_path / "same.wav"))
    assert sr3 == 8000 and len(z) == n
    with pytest.raises(SystemExit, match="in-place"):
        wav_resample.main([str(src), "-o", str(src), "--rate", "16000"])


def test_sprite_rotate(tmp_path):
    im = Image.new("RGBA", (2, 3), (0, 0, 0, 0))
    im.putpixel((0, 0), (255, 0, 0, 255))
    im.putpixel((1, 2), (0, 0, 255, 255))
    src = tmp_path / "a.png"
    im.save(src)
    out = tmp_path / "r90.png"
    assert sprite_rotate.main([str(src), "-o", str(out), "--angle", "90",
                               "--json", str(tmp_path / "r.json")]) == 0
    got = Image.open(out)
    assert got.size == (3, 2)
    # CCW 90: (0,0) red -> (0, 1) in 3x2? Wait: PIL ROTATE_90 is CCW,
    # (x,y) -> (y, w-1-x): (0,0)->(0,1), (1,2)->(2,0)
    assert got.getpixel((0, 1))[:3] == (255, 0, 0)
    assert got.getpixel((2, 0))[:3] == (0, 0, 255)
    out180 = tmp_path / "r180.png"
    assert sprite_rotate.main([str(src), "-o", str(out180), "--angle", "180"]) == 0
    g2 = Image.open(out180)
    assert g2.size == (2, 3) and g2.getpixel((1, 2))[:3] == (255, 0, 0)
    # folder of inputs
    d = tmp_path / "in"
    d.mkdir()
    im.save(d / "a.png")
    im.save(d / "b.png")
    od = tmp_path / "rot"
    assert sprite_rotate.main([str(d), "-o", str(od), "--angle", "270"]) == 0
    assert (od / "a.png").exists() and (od / "b.png").exists()
    with pytest.raises(SystemExit, match="in-place"):
        sprite_rotate.main([str(src), "-o", str(src), "--angle", "90"])


def test_tileset_renumber(tmp_path):
    ts = {
        "name": "ground", "tilewidth": 8, "tileheight": 8, "tilecount": 4, "columns": 4,
        "image": "g.png",
        "tiles": [
            {"id": 0, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 100}]},
            {"id": 1},
        ],
        "wangsets": [{"name": "w", "wangtiles": [{"tileid": 0, "wangid": [0, 0, 0, 0, 0, 0, 0, 0]}]}],
    }
    tsp = tmp_path / "g.tsj"
    json.dump(ts, open(tsp, "w"))
    m = {
        "type": "map", "width": 2, "height": 1, "tilewidth": 8, "tileheight": 8,
        "orientation": "orthogonal",
        "tilesets": [{"firstgid": 1, "source": "g.tsj", "name": "ground"}],
        "layers": [{"type": "tilelayer", "name": "g", "width": 2, "height": 1,
                    "data": [1, 2]}],  # local 0 and 1
    }
    mp = tmp_path / "level.json"
    json.dump(m, open(mp, "w"))
    out_ts = tmp_path / "g2.tsj"
    assert tileset_renumber.main([
        str(tsp), "-o", str(out_ts), "--offset", "10", "--map", str(mp),
        "--tileset-name", "ground", "--json", str(tmp_path / "r.json"),
    ]) == 0
    ts2 = json.load(open(out_ts))
    ids = sorted(t["id"] for t in ts2["tiles"])
    assert ids == [10, 11]
    assert ts2["tiles"][0]["animation"][1]["tileid"] == 11
    assert ts2["wangsets"][0]["wangtiles"][0]["tileid"] == 10
    rec = json.load(open(tmp_path / "r.json"))
    mout = json.load(open(rec["maps"][0]["out"]))
    # firstgid 1, local 0->10, 1->11 => GIDs 11, 12
    assert mout["layers"][0]["data"] == [11, 12]
    # explicit remap
    assert tileset_renumber.main([str(tsp), "-o", str(tmp_path / "swap.tsj"), "--remap", "0=1,1=0"]) == 0
    swap = json.load(open(tmp_path / "swap.tsj"))
    assert {t["id"] for t in swap["tiles"]} == {0, 1}
    with pytest.raises(SystemExit, match="in-place"):
        tileset_renumber.main([str(tsp), "-o", str(tsp), "--offset", "1"])


def _box_gltf(path, translation=(4, 0, 0)):
    # Unit box around the origin as POSITION min/max, root translated.
    js = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "translation": list(translation)}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"min": [-1, -1, -1], "max": [1, 1, 1], "componentType": 5126, "count": 8, "type": "VEC3"}],
    }
    json.dump(js, open(path, "w"))
    return path


def test_glb_center(tmp_path):
    src = _box_gltf(tmp_path / "a.gltf", (4, 0, 0))
    out = tmp_path / "c.gltf"
    assert glb_center.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    # before centre is (4,0,0); after should sit on the origin
    after = rec["after"]
    mid = [(a + b) / 2 for a, b in zip(after["min"], after["max"])]
    assert all(abs(v) < 1e-6 for v in mid)
    js = json.load(open(out))
    t = js["nodes"][0]["translation"]
    assert abs(t[0] - 0) < 1e-6 and abs(t[1]) < 1e-6
    assert glb_center.main([str(src), "--report"]) == 0
    (tmp_path / "no.obj").write_text("v 0 0 0\n")
    with pytest.raises(SystemExit, match="obj-recenter"):
        glb_center.main([str(tmp_path / "no.obj"), "-o", str(tmp_path / "x.glb")])
    with pytest.raises(SystemExit, match="in-place"):
        glb_center.main([str(src), "-o", str(src)])


def test_sfx_normalize_lufs(tmp_path):
    sr = 8000
    n = 8000  # 1 s, long enough for gated LUFS
    t = np.linspace(0, 1, n, endpoint=False)
    x = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1).astype(np.float32)
    src = _wav(tmp_path / "t.wav", x, sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 100, 400))
    out = tmp_path / "l.wav"
    assert sfx_normalize.main([str(src), "-o", str(out), "--lufs", "-16", "--max-true-peak", "-1",
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["mode"] == "lufs"
    f = rec["files"][0]
    assert f["status"] in ("ok", "peak-capped")
    assert f["lufs_out"] is not None
    # landed near the target or was peak-capped under the ceiling
    if f["status"] == "ok":
        assert abs(f["lufs_out"] + 16) < 1.2
    assert f["true_peak_out_db"] <= -1.0 + 0.3
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 100 and loops[0]["end"] == 400
    # peak path is unchanged when --lufs is omitted
    peak = tmp_path / "p.wav"
    assert sfx_normalize.main([str(src), "-o", str(peak), "--peak", "-1"]) == 0
    y, _ = audio_tidy.read_wav(str(peak))
    assert 0.88 < float(np.max(np.abs(y))) < 0.90
    with pytest.raises(SystemExit, match="in-place"):
        sfx_normalize.main([str(src), "-o", str(src), "--lufs", "-16"])
