"""Batch 28 tools: self-contained tests (no samples/ dependency)."""
import json, os

import numpy as np
import pytest
from PIL import Image

import atlas_json, atlas_rename, audio_tidy, glb_attr_drop, glb_lod, jump_arc
import loc_join, loc_split, map_blank, obj_to_glb, obj_validate, sprite_pad
import sprite_unpad, tmx_gid_usage, wav_loop_meta, wav_silence


def _wav(path, x, sr=8000):
    audio_tidy.write_wav(str(path), np.asarray(x, dtype=np.float32), sr, bits=16)
    return path


def _atlas(path, image_name, frames, size):
    data = {
        "frames": {
            name: {
                "frame": {"x": fr[0], "y": fr[1], "w": fr[2], "h": fr[3]},
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": fr[2], "h": fr[3]},
                "sourceSize": {"w": fr[2], "h": fr[3]},
            }
            for name, fr in frames.items()
        },
        "meta": {"image": image_name, "size": {"w": size[0], "h": size[1]},
                 "format": "RGBA8888", "scale": "1"},
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def test_loc_join(tmp_path):
    src = tmp_path / "strings.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Au revoir\n")
    langs = tmp_path / "langs"
    assert loc_split.main([str(src), "-o", str(langs)]) == 0
    out = tmp_path / "joined.csv"
    assert loc_join.main([str(langs), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["languages"] == ["en", "fr"] and rec["keys"] == 2
    text = out.read_text()
    assert text.splitlines()[0] == "id,en,fr"
    assert "ui.hello,Hello,Bonjour" in text
    # union of keys, empty missing cell, --langs order
    (tmp_path / "a.csv").write_text("id,de\nui.hello,Hallo\nonly.de,Nur\n")
    out2 = tmp_path / "wide.csv"
    assert loc_join.main([str(langs / "strings_en.csv"), str(tmp_path / "a.csv"),
                          "-o", str(out2), "--langs", "de,en"]) == 0
    lines = out2.read_text().splitlines()
    assert lines[0] == "id,de,en"
    rows = {r.split(",")[0]: r for r in lines[1:]}
    assert rows["ui.hello"] == "ui.hello,Hallo,Hello"
    assert rows["only.de"] == "only.de,Nur,"
    with pytest.raises(SystemExit):
        loc_join.main([str(out), "-o", str(out)])


def test_map_blank(tmp_path):
    out = tmp_path / "m.json"
    assert map_blank.main(["-o", str(out), "--size", "8x4", "--tile", "16", "--layers", "ground,fg",
                           "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["size"] == [8, 4] and rec["layers"] == ["ground", "fg"]
    m = json.load(open(out))
    assert m["width"] == 8 and m["height"] == 4 and m["tilewidth"] == 16
    assert m["orientation"] == "orthogonal" and m["infinite"] is False
    assert [l["name"] for l in m["layers"]] == ["ground", "fg"]
    assert m["layers"][0]["data"] == [0] * 32
    out2 = tmp_path / "t.json"
    assert map_blank.main(["-o", str(out2), "--size", "2x2", "--tileset", "tiles.png",
                           "--tilecount", "4", "--columns", "2"]) == 0
    assert json.load(open(out2))["tilesets"][0]["firstgid"] == 1
    assert json.load(open(out2))["tilesets"][0]["tilecount"] == 4


def test_obj_validate(tmp_path):
    good = tmp_path / "ok.obj"
    good.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert obj_validate.main([str(good), "--json", str(tmp_path / "ok.json")]) == 0
    rec = json.load(open(tmp_path / "ok.json"))
    assert rec["ok"] and rec["faces"] == 1 and rec["errors"] == []
    bad = tmp_path / "bad.obj"
    bad.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n")
    assert obj_validate.main([str(bad), "--json", str(tmp_path / "bad.json")]) == 1
    assert any(e["code"] == "bad-index" for e in json.load(open(tmp_path / "bad.json"))["errors"])
    deg = tmp_path / "deg.obj"
    deg.write_text("v 0 0 0\nv 1 0 0\nv 2 0 0\nf 1 2 3\n")
    assert obj_validate.main([str(deg), "--json", str(tmp_path / "deg.json")]) == 1
    assert any(e["code"] == "degenerate" for e in json.load(open(tmp_path / "deg.json"))["errors"])
    warn = tmp_path / "w.obj"
    warn.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nv 9 9 9\nf 1 2 3\n")
    assert obj_validate.main([str(warn), "--json", str(tmp_path / "w.json")]) == 0
    assert json.load(open(tmp_path / "w.json"))["warnings"]
    assert obj_validate.main([str(warn), "--strict"]) == 1
    with pytest.raises(SystemExit):
        obj_validate.main([str(good), "--json", str(good)])


def test_wav_silence(tmp_path):
    quiet = tmp_path / "q.wav"
    assert wav_silence.main(["-o", str(quiet), "--duration", "0.25", "--rate", "8000",
                             "--json", str(tmp_path / "g.json")]) == 0
    rec = json.load(open(tmp_path / "g.json"))
    assert rec["mode"] == "generate" and rec["frames"] == 2000
    y, sr = audio_tidy.read_wav(str(quiet))
    assert sr == 8000 and len(y) == 2000 and np.max(np.abs(y)) == 0
    t = np.linspace(0, 1, 8000, endpoint=False)
    src = _wav(tmp_path / "a.wav", (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 10, 400))
    ins = tmp_path / "ins.wav"
    assert wav_silence.main([str(src), "-o", str(ins), "--at", "0", "--duration", "0.1",
                             "--json", str(tmp_path / "i.json")]) == 0
    assert json.load(open(tmp_path / "i.json"))["mode"] == "insert"
    yi, _ = audio_tidy.read_wav(str(ins))
    assert len(yi) == 8000 + 800  # 0.1s at 8k
    assert np.max(np.abs(yi[:800])) == 0
    loops = wav_loop_meta.read_loops(ins.read_bytes())
    assert loops and loops[0]["start"] == 10 + 800 and loops[0]["end"] == 400 + 800
    muted = tmp_path / "m.wav"
    assert wav_silence.main([str(src), "-o", str(muted), "--replace", "0.1,0.2"]) == 0
    ym, _ = audio_tidy.read_wav(str(muted))
    assert len(ym) == 8000
    assert np.max(np.abs(ym[800:1600] if False else ym[int(0.1 * 8000):int(0.2 * 8000)])) == 0
    with pytest.raises(SystemExit):
        wav_silence.main([str(src), "-o", str(src), "--duration", "0.01", "--at", "0"])


def test_sprite_unpad(tmp_path):
    src = tmp_path / "s.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(src)
    padded = tmp_path / "p.png"
    assert sprite_pad.main([str(src), "-o", str(padded), "--pad", "2"]) == 0
    out = tmp_path / "u.png"
    assert sprite_unpad.main([str(padded), "-o", str(out), "--pad", "2",
                              "--json", str(tmp_path / "r.json")]) == 0
    im = Image.open(out)
    assert im.size == (4, 4)
    assert im.getpixel((0, 0))[:3] == (255, 0, 0)
    # atlas rewrite (source canvas only)
    sheet = tmp_path / "sheet.png"
    Image.new("RGBA", (4, 2), (0, 0, 255, 255)).save(sheet)
    atlas = _atlas(tmp_path / "sheet.json", "sheet.png",
                   {"a": (0, 0, 2, 2), "b": (2, 0, 2, 2)}, (4, 2))
    # first pad the atlas source, then unpad it back
    padded_a = tmp_path / "padded.json"
    assert sprite_pad.main([str(atlas), "-o", str(tmp_path / "unused.png"), "--pad", "1,2,3,4",
                            "--atlas-out", str(padded_a)]) == 0
    dest_a = tmp_path / "unpadded.json"
    assert sprite_unpad.main([str(padded_a), "-o", str(tmp_path / "unused2.png"), "--pad", "1,2,3,4",
                              "--atlas-out", str(dest_a)]) == 0
    frames = dict(atlas_json.load(str(dest_a))[1])
    assert frames["a"]["sourceSize"] == {"w": 2, "h": 2}
    assert frames["a"]["spriteSourceSize"]["x"] == 0 and frames["a"]["spriteSourceSize"]["y"] == 0
    with pytest.raises(SystemExit):
        sprite_unpad.main([str(src), "-o", str(src), "--pad", "1"])


def test_glb_attr_drop(tmp_path):
    obj = tmp_path / "p.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nvn 0 0 1\nf 1//1 2//1 3//1\n")
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path)]) == 0
    glb = tmp_path / "p.glb"
    assert glb.is_file()
    gltf0, _ = glb_lod.load_glb(str(glb))
    attrs0 = gltf0["meshes"][0]["primitives"][0]["attributes"]
    out = tmp_path / "slim.glb"
    # drop whatever extra attr is present; NORMAL is typical
    drop = "NORMAL" if "NORMAL" in attrs0 else list(k for k in attrs0 if k != "POSITION")[0]
    assert glb_attr_drop.main([str(glb), "-o", str(out), "--drop", drop,
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["dropped"] >= 1
    gltf, _bin = glb_lod.load_glb(str(out))
    attrs = gltf["meshes"][0]["primitives"][0]["attributes"]
    assert "POSITION" in attrs and drop not in attrs
    with pytest.raises(SystemExit):
        glb_attr_drop.main([str(glb), "-o", str(glb), "--drop", "NORMAL"])
    with pytest.raises(SystemExit):
        glb_attr_drop.main([str(glb), "-o", str(tmp_path / "x.glb"), "--drop", "POSITION"])


def test_tmx_gid_usage(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 4, "height": 2, "tilewidth": 8, "tileheight": 8,
        "tilesets": [
            {"name": "ground", "firstgid": 1, "tilecount": 4, "columns": 2},
            {"name": "unused", "firstgid": 20, "tilecount": 2, "columns": 2},
        ],
        "layers": [
            {"type": "tilelayer", "name": "fg", "width": 4, "height": 2,
             "data": [1, 2, 1, 0, 0x80000000 | 2, 0, 0, 3]},
        ],
    }))
    assert tmx_gid_usage.main([str(src), "--json", str(tmp_path / "u.json"),
                               "-o", str(tmp_path / "u.csv")]) == 0
    rec = json.load(open(tmp_path / "u.json"))
    assert rec["used_gids"] == 3 and rec["placed"] == 5
    by = {r["gid"]: r for r in rec["gids"]}
    assert by[1]["count"] == 2 and by[1]["tileset"] == "ground" and by[1]["local_id"] == 0
    assert by[2]["flip_h"] == 1 and by[2]["count"] == 2
    assert "unused" in rec["unused_tilesets"]
    assert tmx_gid_usage.main([str(src), "--json", str(tmp_path / "u2.json"),
                               "--fail-on-unused-tileset"]) == 1
    with pytest.raises(SystemExit):
        tmx_gid_usage.main([str(src), "--json", str(src)])


def test_atlas_rename(tmp_path):
    atlas = _atlas(tmp_path / "a.json", "a.png",
                   {"walk_01": (0, 0, 2, 2), "walk_02": (2, 0, 2, 2)}, (4, 2))
    out = tmp_path / "b.json"
    assert atlas_rename.main([str(atlas), "-o", str(out), "--pattern", r"walk_(\d+)",
                              "--replace", r"hero_\1", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["renamed"] == 2
    data, items, _ = atlas_json.load(str(out))
    names = [n for n, _ in items]
    assert names == ["hero_01", "hero_02"]
    assert dict(items)["hero_01"]["frame"] == {"x": 0, "y": 0, "w": 2, "h": 2}
    out2 = tmp_path / "c.json"
    assert atlas_rename.main([str(atlas), "-o", str(out2), "--map", "walk_01=idle_01"]) == 0
    assert "idle_01" in dict(atlas_json.load(str(out2))[1])
    with pytest.raises(SystemExit):
        atlas_rename.main([str(atlas), "-o", str(tmp_path / "bad.json"),
                           "--map", "walk_01=same,walk_02=same"])
    with pytest.raises(SystemExit):
        atlas_rename.main([str(atlas), "-o", str(atlas), "--pattern", "walk", "--replace", "run"])


def test_jump_arc_reports_end(tmp_path):
    assert jump_arc.main(["-o", str(tmp_path / "arc.png"), "--width", "200", "--height", "120",
                          "--start", "20,100", "--jump-v", "180", "--speed", "80", "--gravity", "600",
                          "--json", str(tmp_path / "arc.json")]) == 0
    rec = json.load(open(tmp_path / "arc.json"))
    assert "end" in rec and len(rec["end"]) == 2
    assert rec["end"][0] > rec["start"][0]
    assert rec["landed"] is True
    assert rec["out_of_bounds"] is False
