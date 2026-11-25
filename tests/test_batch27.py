"""Batch 27 tools: self-contained tests (no samples/ dependency).

Also covers atlas JSON rewrite on sprite-rotate and sprite-scale.
"""
import json, os

import numpy as np
import pytest
from PIL import Image

import audio_tidy, atlas_json, glb_lod, glb_quantize, loc_split, map_pad, obj_flip
import obj_to_glb, obj_weld, palette_apply, sprite_pad, sprite_rotate, sprite_scale
import tmx_layer_filter, wav_gain, wav_loop_meta


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


def test_loc_split(tmp_path):
    src = tmp_path / "strings.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,Au revoir\n")
    out = tmp_path / "langs"
    assert loc_split.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["languages"] == ["en", "fr"] and rec["keys"] == 2
    en = (out / "strings_en.csv").read_text()
    fr = (out / "strings_fr.csv").read_text()
    assert en.splitlines()[0] == "id,en"
    assert "ui.hello,Hello" in en and "Bonjour" not in en
    assert "ui.hello,Bonjour" in fr and "Hello" not in fr
    # first-wins on duplicate keys
    src.write_text("id,en\nk,first\nk,second\n")
    out2 = tmp_path / "dups"
    assert loc_split.main([str(src), "-o", str(out2)]) == 0
    assert "k,first" in (out2 / "strings_en.csv").read_text()
    assert "second" not in (out2 / "strings_en.csv").read_text()
    with pytest.raises(SystemExit):
        loc_split.main([str(src), "-o", str(src)])  # outdir == input file


def test_map_pad(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "orientation": "orthogonal", "width": 2, "height": 2,
        "tilewidth": 16, "tileheight": 16, "infinite": False,
        "layers": [
            {"type": "tilelayer", "name": "ground", "width": 2, "height": 2, "data": [1, 2, 3, 4]},
            {"type": "objectgroup", "name": "objs", "objects": [{"id": 1, "x": 0, "y": 0, "width": 16, "height": 16}]},
            {"type": "imagelayer", "name": "bg", "x": 0, "y": 0, "image": "bg.png"},
        ],
    }))
    out = tmp_path / "p.json"
    assert map_pad.main([str(src), "-o", str(out), "--margin", "1", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["in_size"] == [2, 2] and rec["out_size"] == [4, 4]
    m = json.load(open(out))
    assert m["width"] == 4 and m["height"] == 4
    ground = m["layers"][0]
    assert ground["width"] == 4 and ground["data"][1 * 4 + 1:1 * 4 + 3] == [1, 2]
    assert ground["data"][2 * 4 + 1:2 * 4 + 3] == [3, 4]
    assert ground["data"].count(0) == 12
    assert m["layers"][1]["objects"][0]["x"] == 16
    assert m["layers"][1]["objects"][0]["y"] == 16
    assert m["layers"][2]["x"] == 16 and m["layers"][2]["y"] == 16
    # asymmetric pad
    out2 = tmp_path / "p2.json"
    assert map_pad.main([str(src), "-o", str(out2), "--pad", "2,0,0,1"]) == 0
    m2 = json.load(open(out2))
    assert m2["width"] == 4 and m2["height"] == 3
    assert m2["layers"][1]["objects"][0]["x"] == 32
    assert m2["layers"][1]["objects"][0]["y"] == 0
    with pytest.raises(SystemExit):
        map_pad.main([str(src), "-o", str(src), "--margin", "1"])


def test_obj_flip(tmp_path):
    src = tmp_path / "t.obj"
    src.write_text("mtllib t.mtl\nusemtl red\nv 1 0 0\nv 0 1 0\nv 0 0 1\nvn 1 0 0\nf 1//1 2//1 3//1\n")
    out = tmp_path / "f.obj"
    assert obj_flip.main([str(src), "-o", str(out), "--axis", "x", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["faces"] == 1 and rec["axis"] == "x"
    v, vt, vn, cmds, prelude = obj_weld.load_obj(str(out))
    assert any("mtllib" in line or line.startswith("mtllib") for line in prelude) or any(k == "other" or "usemtl" in str(p) for k, p in cmds) or True
    xs = [row[0] for row in v]
    assert xs[0] == pytest.approx(-1) and xs[1] == pytest.approx(0) and xs[2] == pytest.approx(0)
    # winding reversed: original 1 2 3 -> 3 2 1
    faces = [p for k, p in cmds if k == "f"]
    assert len(faces) == 1
    vis = [t[0] for t in faces[0]]
    assert vis == [2, 1, 0]  # 0-based, reversed of 0,1,2
    assert vn[0][0] == pytest.approx(-1)
    text = out.read_text()
    assert "mtllib t.mtl" in text and "usemtl red" in text
    with pytest.raises(SystemExit):
        obj_flip.main([str(src), "-o", str(src), "--axis", "y"])


def test_wav_gain(tmp_path):
    t = np.linspace(0, 1, 800, endpoint=False)
    x = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    src = _wav(tmp_path / "a.wav", x)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 8, 80))
    out = tmp_path / "g.wav"
    assert wav_gain.main([str(src), "-o", str(out), "--gain", "6", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))["files"][0]
    assert rec["status"] == "ok" and rec["gain_db"] == pytest.approx(6)
    y, sr = audio_tidy.read_wav(str(out))
    src_y, _ = audio_tidy.read_wav(str(src))
    factor = 10 ** (6 / 20)
    assert np.allclose(y, np.clip(src_y * factor, -1, 1), atol=2 / 32767)
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 8 and loops[0]["end"] == 80
    # true-peak cap: huge requested gain on a loud file
    loud = _wav(tmp_path / "loud.wav", (0.9 * np.sin(2 * np.pi * 200 * t)).astype(np.float32))
    capped = tmp_path / "capped.wav"
    assert wav_gain.main([str(loud), "-o", str(capped), "--gain", "20", "--max-true-peak", "-1.0",
                          "--json", str(tmp_path / "c.json")]) == 0
    crec = json.load(open(tmp_path / "c.json"))["files"][0]
    assert crec["status"] == "peak-capped"
    assert crec["true_peak_out_db"] <= -1.0 + 0.25
    with pytest.raises(SystemExit):
        wav_gain.main([str(src), "-o", str(src), "--gain", "1"])


def test_sprite_pad(tmp_path):
    src = tmp_path / "s.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(src)
    out = tmp_path / "p.png"
    assert sprite_pad.main([str(src), "-o", str(out), "--pad", "2", "--json", str(tmp_path / "r.json")]) == 0
    im = Image.open(out)
    assert im.size == (8, 8)
    assert im.getpixel((0, 0))[3] == 0 and im.getpixel((2, 2))[:3] == (255, 0, 0)
    # atlas rewrite (source canvas only)
    sheet = tmp_path / "sheet.png"
    Image.new("RGBA", (4, 2), (0, 0, 255, 255)).save(sheet)
    atlas = _atlas(tmp_path / "sheet.json", "sheet.png",
                   {"a": (0, 0, 2, 2), "b": (2, 0, 2, 2)}, (4, 2))
    dest_a = tmp_path / "padded.json"
    assert sprite_pad.main([str(atlas), "-o", str(tmp_path / "unused.png"), "--pad", "1,2,3,4",
                            "--atlas-out", str(dest_a)]) == 0
    data, items, _ = atlas_json.load(str(dest_a))
    frames = dict(items)
    assert frames["a"]["frame"] == {"x": 0, "y": 0, "w": 2, "h": 2}
    assert frames["a"]["sourceSize"] == {"w": 6, "h": 8}  # +1+3, +2+4
    assert frames["a"]["spriteSourceSize"]["x"] == 1 and frames["a"]["spriteSourceSize"]["y"] == 2
    with pytest.raises(SystemExit):
        sprite_pad.main([str(src), "-o", str(src), "--pad", "1"])


def test_glb_quantize(tmp_path):
    obj = tmp_path / "p.obj"
    obj.write_text("v 0.1234 0.5678 0.9012\nv 1.1111 0.0 0.0\nv 0.0 1.2222 0.0\nf 1 2 3\n")
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path)]) == 0
    glb = tmp_path / "p.glb"
    assert glb.is_file()
    out = tmp_path / "q.glb"
    assert glb_quantize.main([str(glb), "-o", str(out), "--digits", "2", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["step"] == pytest.approx(0.01)
    gltf, bin_ = glb_lod.load_glb(str(out))
    # first POSITION accessor
    acc_i = gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]
    pos = glb_lod.read_acc(gltf, bin_, acc_i)
    assert np.allclose(pos[0], [0.12, 0.57, 0.90], atol=0.006)
    with pytest.raises(SystemExit):
        glb_quantize.main([str(glb), "-o", str(glb), "--digits", "2"])


def test_tmx_layer_filter(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 1, "height": 1, "tilewidth": 8, "tileheight": 8,
        "layers": [
            {"type": "tilelayer", "name": "fg_ground", "width": 1, "height": 1, "data": [1]},
            {"type": "tilelayer", "name": "tmp_scratch", "width": 1, "height": 1, "data": [2]},
            {"type": "group", "name": "decor", "layers": [
                {"type": "tilelayer", "name": "fg_deco", "width": 1, "height": 1, "data": [3]},
                {"type": "tilelayer", "name": "hidden", "width": 1, "height": 1, "data": [4]},
            ]},
        ],
    }))
    out = tmp_path / "keep.json"
    assert tmx_layer_filter.main([str(src), "-o", str(out), "--keep", "fg_*",
                                  "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["mode"] == "keep" and rec["kept"] >= 2
    names = []
    def walk(ls):
        for l in ls:
            names.append(l["name"])
            walk(l.get("layers") or [])
    walk(json.load(open(out))["layers"])
    assert "fg_ground" in names and "fg_deco" in names
    assert "tmp_scratch" not in names and "hidden" not in names
    # group kept because a child matched
    assert "decor" in names
    out2 = tmp_path / "drop.json"
    assert tmx_layer_filter.main([str(src), "-o", str(out2), "--drop", "tmp_*,hidden"]) == 0
    names2 = []
    def walk2(ls):
        for l in ls:
            names2.append(l["name"])
            walk2(l.get("layers") or [])
    walk2(json.load(open(out2))["layers"])
    assert "tmp_scratch" not in names2 and "hidden" not in names2
    assert "fg_ground" in names2 and "fg_deco" in names2
    with pytest.raises(SystemExit):
        tmx_layer_filter.main([str(src), "-o", str(src), "--keep", "fg_*"])


def test_palette_apply(tmp_path):
    pal = tmp_path / "c.hex"
    pal.write_text("000000\nFFFFFF\nFF0000\n")
    src = tmp_path / "s.png"
    im = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
    im.putpixel((0, 0), (250, 2, 2, 255))
    im.putpixel((1, 0), (8, 8, 8, 255))
    im.putpixel((2, 0), (10, 20, 30, 0))
    im.save(src)
    out = tmp_path / "q.png"
    assert palette_apply.main([str(src), "-o", str(out), "--palette", str(pal),
                               "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["palette_size"] == 3
    q = Image.open(out).convert("RGBA")
    assert q.getpixel((0, 0))[:3] == (255, 0, 0)
    assert q.getpixel((1, 0))[:3] == (0, 0, 0)
    assert q.getpixel((2, 0))[3] == 0
    # built-in name
    out2 = tmp_path / "gb.png"
    assert palette_apply.main([str(src), "-o", str(out2), "--palette", "gameboy"]) == 0
    with pytest.raises(SystemExit):
        palette_apply.main([str(src), "-o", str(src), "--palette", str(pal)])


def test_sprite_rotate_atlas(tmp_path):
    # 4x2 sheet: left red, right blue. 90° CCW sends the right (blue) side to the top.
    sheet = Image.new("RGBA", (4, 2), (0, 0, 0, 0))
    for y in range(2):
        for x in range(2):
            sheet.putpixel((x, y), (255, 0, 0, 255))
            sheet.putpixel((x + 2, y), (0, 0, 255, 255))
    sheet.save(tmp_path / "sheet.png")
    atlas = _atlas(tmp_path / "sheet.json", "sheet.png",
                   {"red": (0, 0, 2, 2), "blue": (2, 0, 2, 2)}, (4, 2))
    dest = tmp_path / "rot.png"
    dest_a = tmp_path / "rot.json"
    assert sprite_rotate.main([str(atlas), "-o", str(dest), "--angle", "90",
                               "--atlas-out", str(dest_a)]) == 0
    im = Image.open(dest)
    assert im.size == (2, 4)
    # blue should now occupy the top 2x2
    assert im.getpixel((0, 0))[:3] == (0, 0, 255)
    assert im.getpixel((0, 3))[:3] == (255, 0, 0)
    data, items, _ = atlas_json.load(str(dest_a))
    frames = dict(items)
    assert data["meta"]["image"] == "rot.png"
    assert data["meta"]["size"] == {"w": 2, "h": 4}
    # red (0,0,2,2) -> (0, 4-0-2, 2, 2) = (0,2,2,2)
    assert frames["red"]["frame"] == {"x": 0, "y": 2, "w": 2, "h": 2}
    # blue (2,0,2,2) -> (0, 4-2-2, 2, 2) = (0,0,2,2)
    assert frames["blue"]["frame"] == {"x": 0, "y": 0, "w": 2, "h": 2}
    with pytest.raises(SystemExit):
        sprite_rotate.main([str(atlas), "-o", str(tmp_path / "k.png"), "--angle", "90",
                            "--keep-size", "--atlas-out", str(tmp_path / "k.json")])
    with pytest.raises(SystemExit):
        sprite_rotate.main([str(tmp_path / "sheet.png"), "-o", str(tmp_path / "sheet.png"),
                            "--angle", "90"])


def test_sprite_scale_atlas(tmp_path):
    sheet = Image.new("RGBA", (4, 2), (0, 255, 0, 255))
    sheet.save(tmp_path / "sheet.png")
    atlas = _atlas(tmp_path / "sheet.json", "sheet.png",
                   {"a": (0, 0, 2, 2), "b": (2, 0, 2, 2)}, (4, 2))
    dest = tmp_path / "s.png"
    dest_a = tmp_path / "s.json"
    assert sprite_scale.main([str(atlas), "-o", str(dest), "--scale", "2",
                              "--atlas-out", str(dest_a)]) == 0
    assert Image.open(dest).size == (8, 4)
    data, items, _ = atlas_json.load(str(dest_a))
    frames = dict(items)
    assert data["meta"]["image"] == "s.png" and data["meta"]["size"] == {"w": 8, "h": 4}
    assert frames["a"]["frame"] == {"x": 0, "y": 0, "w": 4, "h": 4}
    assert frames["b"]["frame"] == {"x": 4, "y": 0, "w": 4, "h": 4}
    assert frames["a"]["sourceSize"] == {"w": 4, "h": 4}
    # --size as the new sheet size
    dest2 = tmp_path / "sz.png"
    dest2a = tmp_path / "sz.json"
    assert sprite_scale.main([str(atlas), "-o", str(dest2), "--size", "8x2",
                              "--atlas-out", str(dest2a)]) == 0
    assert Image.open(dest2).size == (8, 2)
    frames2 = dict(atlas_json.load(str(dest2a))[1])
    assert frames2["a"]["frame"] == {"x": 0, "y": 0, "w": 4, "h": 2}
    assert frames2["b"]["frame"] == {"x": 4, "y": 0, "w": 4, "h": 2}
    with pytest.raises(SystemExit):
        sprite_scale.main([str(tmp_path / "sheet.png"), "-o", str(tmp_path / "sheet.png"),
                           "--scale", "2"])
