"""Batch 24 tools: self-contained tests (no samples/ dependency)."""
import json, os

import numpy as np
import pytest
from PIL import Image

import audio_tidy, loc_merge, map_diff, map_scale, obj_split, sfx_normalize
import sprite_recolor, tileset_merge, tileset_split, tmx_encode, wav_chan_swap, wav_loop_meta


def _wav(path, x, sr=8000):
    audio_tidy.write_wav(str(path), np.asarray(x, dtype=np.float32), sr, bits=16)
    return path


def test_loc_merge(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Au revoir\nui.onlya,OnlyA,SeulA\n")
    b.write_text("id,en,de\nui.hello,Hello,Hallo\nui.bye,BYE,Tschuss\nui.onlyb,OnlyB,NurB\n")
    out = tmp_path / "m.csv"
    rc = loc_merge.main([str(a), str(b), "-o", str(out), "--json", str(tmp_path / "r.json")])
    assert rc == 1  # collision on ui.bye + missing keys
    rec = json.load(open(tmp_path / "r.json"))
    assert "ui.onlya" in rec["only_in_a"] and "ui.onlyb" in rec["only_in_b"]
    assert any(c["key"] == "ui.bye" and c["column"] == "en" for c in rec["collisions"])
    rows = {r.split(",")[0]: r for r in out.read_text().strip().splitlines()}
    # prefer a (default): Bye stays; de column added
    assert "id,en,fr,de" in out.read_text().splitlines()[0]
    assert "ui.bye,Bye,Au revoir," in out.read_text()
    assert loc_merge.main([str(a), str(b), "-o", str(tmp_path / "m2.csv"), "--prefer", "b", "--no-fail"]) == 0
    assert "ui.bye,BYE,Au revoir," in (tmp_path / "m2.csv").read_text()
    with pytest.raises(SystemExit, match="collision"):
        loc_merge.main([str(a), str(b), "-o", str(tmp_path / "m3.csv"), "--prefer", "fail"])
    assert not (tmp_path / "m3.csv").exists()
    with pytest.raises(SystemExit, match="in-place"):
        loc_merge.main([str(a), str(b), "-o", str(a)])


def test_map_scale(tmp_path):
    m = {
        "type": "map", "width": 2, "height": 2, "tilewidth": 16, "tileheight": 16,
        "orientation": "orthogonal",
        "layers": [
            {"type": "tilelayer", "name": "g", "width": 2, "height": 2, "offsetx": 8, "data": [1, 2, 3, 4]},
            {"type": "objectgroup", "name": "o", "objects": [
                {"id": 1, "x": 16, "y": 8, "width": 16, "height": 8,
                 "polygon": [{"x": 0, "y": 0}, {"x": 16, "y": 8}]},
            ]},
        ],
    }
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_scale.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m32.json"),
                           "--factor", "2", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "m32.json"))
    assert out["tilewidth"] == 32 and out["tileheight"] == 32
    assert out["width"] == 2 and out["layers"][0]["data"] == [1, 2, 3, 4]
    assert out["layers"][0]["offsetx"] == 16
    obj = out["layers"][1]["objects"][0]
    assert obj["x"] == 32 and obj["y"] == 16 and obj["width"] == 32 and obj["height"] == 16
    assert obj["polygon"] == [{"x": 0, "y": 0}, {"x": 32, "y": 16}]
    assert map_scale.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m8.json"), "--tile", "8"]) == 0
    small = json.load(open(tmp_path / "m8.json"))
    assert small["tilewidth"] == 8 and small["layers"][1]["objects"][0]["x"] == 8
    iso = dict(m, orientation="isometric")
    json.dump(iso, open(tmp_path / "iso.json", "w"))
    with pytest.raises(SystemExit, match="isometric"):
        map_scale.main([str(tmp_path / "iso.json"), "-o", str(tmp_path / "x.json"), "--factor", "2"])
    with pytest.raises(SystemExit, match="in-place"):
        map_scale.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json"), "--factor", "2"])


def test_obj_split(tmp_path):
    src = tmp_path / "props.obj"
    src.write_text(
        "mtllib props.mtl\n"
        "o cube\n"
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "f 1 2 3\nf 1 3 4\n"
        "o wedge\n"
        "v 10 0 0\nv 11 0 0\nv 10 1 0\n"
        "vt 0 0\nvt 1 0\nvt 0 1\n"
        "f 5/1 6/2 7/3\n"
    )
    assert obj_split.main([str(src), "-o", str(tmp_path / "parts"), "--by", "o",
                           "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["count"] == 2
    names = {os.path.basename(p["out"]) for p in rec["parts"]}
    assert names == {"cube.obj", "wedge.obj"}
    cube = (tmp_path / "parts" / "cube.obj").read_text()
    assert "mtllib props.mtl" in cube
    assert cube.count("v ") == 4 and cube.count("f ") == 2
    assert "f 1 2 3" in cube and "f 1 3 4" in cube
    wedge = (tmp_path / "parts" / "wedge.obj").read_text()
    assert wedge.count("v ") == 3 and "f 1/1 2/2 3/3" in wedge
    lonely = tmp_path / "solo.obj"
    lonely.write_text("o solo\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    with pytest.raises(SystemExit, match="in-place"):
        obj_split.main([str(lonely), "-o", str(tmp_path)])


def test_sfx_normalize(tmp_path):
    src = tmp_path / "a.wav"
    n, sr = 200, 8000
    t = np.linspace(0, n / sr, n, endpoint=False)
    x = (0.5 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1).astype(np.float32)
    _wav(src, x, sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 10, 40))
    out = tmp_path / "n.wav"
    assert sfx_normalize.main([str(src), "-o", str(out), "--peak", "-1",
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))["files"][0]
    assert rec["status"] == "ok"
    y, sr2 = audio_tidy.read_wav(str(out))
    peak = float(np.max(np.abs(y)))
    # -1 dBFS ≈ 0.89125
    assert 0.88 < peak < 0.90
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 10 and loops[0]["end"] == 40
    silent = tmp_path / "z.wav"
    _wav(silent, np.zeros((50, 1), np.float32), sr)
    assert sfx_normalize.main([str(silent), "-o", str(tmp_path / "z2.wav"), "--json", str(tmp_path / "s.json")]) == 0
    assert json.load(open(tmp_path / "s.json"))["files"][0]["status"] == "silent"
    with pytest.raises(SystemExit, match="in-place"):
        sfx_normalize.main([str(src), "-o", str(src), "--peak", "-1"])


def test_tileset_split(tmp_path):
    # 4 tiles 8x8 in a row, distinct colours; animation on tile 0->1 (stays in A)
    sheet = Image.new("RGBA", (32, 8), (0, 0, 0, 0))
    cols = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    for i, c in enumerate(cols):
        sheet.paste(Image.new("RGBA", (8, 8), c), (i * 8, 0))
    sheet.save(tmp_path / "t.png")
    ts = {"name": "T", "tilewidth": 8, "tileheight": 8, "tilecount": 4, "columns": 4,
          "image": "t.png", "imagewidth": 32, "imageheight": 8,
          "tiles": [{"id": 0, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 100}]}]}
    json.dump(ts, open(tmp_path / "t.tsj", "w"))
    m = {"type": "map", "width": 4, "height": 1, "tilewidth": 8, "tileheight": 8,
         "tilesets": [{"firstgid": 1, "source": "t.tsj", "name": "T"}],
         "layers": [{"type": "tilelayer", "name": "g", "width": 4, "height": 1, "data": [1, 2, 3, 4]}]}
    json.dump(m, open(tmp_path / "map.json", "w"))
    assert tileset_split.main([
        str(tmp_path / "t.tsj"), "-o", str(tmp_path / "parts" / "t"), "--at", "2",
        "--map", str(tmp_path / "map.json"), "--map-out", str(tmp_path / "map2.json"),
        "--json", str(tmp_path / "r.json"),
    ]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["ids_a"] == [0, 1] and rec["ids_b"] == [2, 3]
    a = json.load(open(tmp_path / "parts" / "t_a.tsj"))
    b = json.load(open(tmp_path / "parts" / "t_b.tsj"))
    assert a["tilecount"] == 2 and b["tilecount"] == 2
    assert (tmp_path / "parts" / "t_a.png").exists() and (tmp_path / "parts" / "t_b.png").exists()
    assert Image.open(tmp_path / "parts" / "t_a.png").getpixel((0, 0))[:3] == (255, 0, 0)
    assert Image.open(tmp_path / "parts" / "t_b.png").getpixel((0, 0))[:3] == (0, 0, 255)
    anim = [t for t in a["tiles"] if t["id"] == 0][0]["animation"]
    assert [f["tileid"] for f in anim] == [0, 1]
    m2 = json.load(open(tmp_path / "map2.json"))
    # prefix split: GIDs unchanged, two tileset entries 1 and 3
    assert m2["layers"][0]["data"] == [1, 2, 3, 4]
    assert [ts["firstgid"] for ts in m2["tilesets"]] == [1, 3]
    # non-prefix --ids remaps
    assert tileset_split.main([
        str(tmp_path / "t.tsj"), "-o", str(tmp_path / "alt" / "t"), "--ids", "0,2",
        "--map", str(tmp_path / "map.json"), "--map-out", str(tmp_path / "map3.json"),
    ]) == 0
    m3 = json.load(open(tmp_path / "map3.json"))
    # A ids 0,2 -> firstgid 1 local 0,1 => gids 1,2; B ids 1,3 -> firstgid 3 local 0,1 => gids 3,4
    # original gids 1,2,3,4 are local 0,1,2,3 -> 1, 3, 2, 4
    assert m3["layers"][0]["data"] == [1, 3, 2, 4]
    with pytest.raises(SystemExit, match="in-place"):
        tileset_split.main([str(tmp_path / "t.tsj"), "-o", str(tmp_path / "x"),
                            "--json", str(tmp_path / "t.tsj")])


def test_wav_chan_swap(tmp_path):
    sr = 8000
    left = np.linspace(0.1, 0.2, 40, dtype=np.float32)
    right = np.linspace(-0.3, -0.1, 40, dtype=np.float32)
    src = tmp_path / "st.wav"
    _wav(src, np.stack([left, right], axis=1), sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 2, 10))
    out = tmp_path / "sw.wav"
    assert wav_chan_swap.main([str(src), "-o", str(out), "--swap", "--json", str(tmp_path / "r.json")]) == 0
    y, _ = audio_tidy.read_wav(str(out))
    assert np.allclose(y[:, 0], right, atol=1e-4) and np.allclose(y[:, 1], left, atol=1e-4)
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 2 and loops[0]["end"] == 10
    quad = tmp_path / "q.wav"
    chans = np.stack([np.full(20, v, np.float32) for v in (0.1, 0.2, 0.3, 0.4)], axis=1)
    _wav(quad, chans, sr)
    assert wav_chan_swap.main([str(quad), "-o", str(tmp_path / "q2.wav"), "--order", "3,2,1,0"]) == 0
    z, _ = audio_tidy.read_wav(str(tmp_path / "q2.wav"))
    assert np.allclose(z[0], [0.4, 0.3, 0.2, 0.1], atol=1e-4)
    with pytest.raises(SystemExit, match="in-place"):
        wav_chan_swap.main([str(src), "-o", str(src), "--swap"])


def test_sprite_recolor(tmp_path):
    img = Image.new("RGBA", (4, 2), (0, 0, 0, 0))
    img.putpixel((0, 0), (255, 0, 0, 255))
    img.putpixel((1, 0), (255, 0, 0, 128))
    img.putpixel((2, 0), (0, 255, 0, 255))
    img.putpixel((3, 0), (0, 0, 255, 200))
    src = tmp_path / "s.png"
    img.save(src)
    out = tmp_path / "o.png"
    assert sprite_recolor.main([str(src), "-o", str(out), "--map", "ff0000:0000ff,00ff00:ffffff",
                                "--json", str(tmp_path / "r.json")]) == 0
    im = Image.open(out)
    assert im.getpixel((0, 0)) == (0, 0, 255, 255)
    assert im.getpixel((1, 0)) == (0, 0, 255, 128)  # alpha kept
    assert im.getpixel((2, 0)) == (255, 255, 255, 255)
    assert im.getpixel((3, 0)) == (0, 0, 255, 200)  # untouched
    (tmp_path / "from.hex").write_text("#0000FF\n")
    (tmp_path / "to.hex").write_text("#010101\n")
    assert sprite_recolor.main([str(out), "-o", str(tmp_path / "p.png"),
                                "--from", str(tmp_path / "from.hex"),
                                "--to", str(tmp_path / "to.hex")]) == 0
    assert Image.open(tmp_path / "p.png").getpixel((0, 0))[:3] == (1, 1, 1)
    with pytest.raises(SystemExit, match="in-place"):
        sprite_recolor.main([str(src), "-o", str(src), "--map", "ff0000:0000ff"])


def test_tmx_encode(tmp_path):
    data = [1, 2, 3, 4, 0x80000005, 6]
    m = {"type": "map", "width": 3, "height": 2, "tilewidth": 16, "tileheight": 16,
         "layers": [{"type": "tilelayer", "name": "g", "width": 3, "height": 2, "data": data}]}
    src = tmp_path / "m.json"
    json.dump(m, open(src, "w"))
    assert tmx_encode.main([str(src), "-o", str(tmp_path / "csv.json"), "--encoding", "csv"]) == 0
    csv_m = json.load(open(tmp_path / "csv.json"))
    assert csv_m["layers"][0]["encoding"] == "csv"
    assert map_diff.decode_tile_data(csv_m["layers"][0]["data"], "csv", None) == data
    assert tmx_encode.main([str(tmp_path / "csv.json"), "-o", str(tmp_path / "z.json"),
                            "--encoding", "base64", "--compression", "zlib"]) == 0
    z = json.load(open(tmp_path / "z.json"))
    assert z["layers"][0]["encoding"] == "base64" and z["layers"][0]["compression"] == "zlib"
    assert map_diff.layer_gids(z["layers"][0]) == data
    assert tmx_encode.main([str(tmp_path / "z.json"), "-o", str(tmp_path / "gz.json"),
                            "--encoding", "base64", "--compression", "gzip"]) == 0
    g = json.load(open(tmp_path / "gz.json"))
    assert g["layers"][0]["compression"] == "gzip"
    assert map_diff.layer_gids(g["layers"][0]) == data
    assert tmx_encode.main([str(tmp_path / "gz.json"), "-o", str(tmp_path / "arr.json"),
                            "--encoding", "array"]) == 0
    arr = json.load(open(tmp_path / "arr.json"))
    assert arr["layers"][0]["data"] == data
    assert "encoding" not in arr["layers"][0]
    # TMX
    tmx = tmp_path / "m.tmx"
    tmx.write_text(
        '<?xml version="1.0"?>\n'
        '<map version="1.10" width="3" height="2" tilewidth="16" tileheight="16" orientation="orthogonal">\n'
        ' <layer name="g" width="3" height="2">\n'
        '  <data encoding="csv">1,2,3,4,5,6</data>\n'
        ' </layer>\n'
        '</map>\n'
    )
    assert tmx_encode.main([str(tmx), "-o", str(tmp_path / "m2.tmx"),
                            "--encoding", "base64", "--compression", "zlib"]) == 0
    import xml.etree.ElementTree as ET
    data_el = ET.parse(tmp_path / "m2.tmx").find(".//data")
    assert data_el.get("encoding") == "base64" and data_el.get("compression") == "zlib"
    gids = map_diff.decode_tile_data(data_el.text, "base64", "zlib")
    assert gids == [1, 2, 3, 4, 5, 6]
    with pytest.raises(SystemExit, match="in-place"):
        tmx_encode.main([str(src), "-o", str(src), "--encoding", "csv"])
