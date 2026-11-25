"""Batch 30 tools: self-contained tests (no samples/ dependency)."""
import json, struct, os

import numpy as np
import pytest
from PIL import Image

import atlas_json, atlas_merge, audio_tidy, glb_extras_strip, glb_lod
import loc_fill, map_outline, obj_drop_unused, obj_to_glb, sprite_align
import tmx_tileset_list, wav_limit, wav_loop_meta


def _wav(path, x, sr=8000):
    audio_tidy.write_wav(str(path), np.asarray(x, dtype=np.float32), sr, bits=16)
    return path


def _atlas(path, image_name, frames, size, sheet=None):
    data = {
        "frames": {
            name: {
                "frame": {"x": fr[0], "y": fr[1], "w": fr[2], "h": fr[3]},
                "rotated": False, "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": fr[2], "h": fr[3]},
                "sourceSize": {"w": fr[2], "h": fr[3]},
            }
            for name, fr in frames.items()
        },
        "meta": {"image": image_name, "size": {"w": size[0], "h": size[1]},
                 "format": "RGBA8888", "scale": "1"},
    }
    path.write_text(json.dumps(data, indent=2))
    if sheet is not None:
        sheet.save(path.parent / image_name)
    return path


def test_loc_fill(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text("id,en,fr\nui.hello,Hello,\nui.bye,Bye,Salut\nempty,,\n")
    out = tmp_path / "f.csv"
    assert loc_fill.main([str(src), "-o", str(out), "--source", "en",
                          "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["filled"] == 1  # ui.hello fr
    rows = {r.split(",")[0]: r for r in out.read_text().splitlines()[1:]}
    assert "Hello" in rows["ui.hello"] and rows["ui.hello"].endswith("Hello")
    assert "Salut" in rows["ui.bye"]  # not overwritten
    # prefix + overwrite
    out2 = tmp_path / "f2.csv"
    assert loc_fill.main([str(src), "-o", str(out2), "--source", "en",
                          "--prefix", "[en] ", "--overwrite"]) == 0
    text = out2.read_text()
    assert "[en] Hello" in text and "[en] Bye" in text
    with pytest.raises(SystemExit):
        loc_fill.main([str(src), "-o", str(src)])


def test_map_outline(tmp_path):
    src = tmp_path / "m.json"
    # 5x3, walls around the edge, open interior
    walls = [
        1, 1, 1, 1, 1,
        1, 0, 0, 0, 1,
        1, 1, 1, 1, 1,
    ]
    src.write_text(json.dumps({
        "type": "map", "width": 5, "height": 3, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "tilelayer", "name": "walls", "width": 5, "height": 3, "data": walls}],
    }))
    assert map_outline.main([str(src), "--solid-layer", "walls",
                             "--json", str(tmp_path / "o.json"),
                             "--png", str(tmp_path / "o.png"),
                             "-o", str(tmp_path / "m2.json")]) == 0
    rec = json.load(open(tmp_path / "o.json"))
    # every solid cell is on the edge or next to a hole, so all 12 wall cells are outline
    assert rec["solid_count"] == 12 and rec["outline_count"] == 12
    assert (tmp_path / "o.png").is_file()
    m2 = json.load(open(tmp_path / "m2.json"))
    names = [l["name"] for l in m2["layers"]]
    assert "outline" in names
    with pytest.raises(SystemExit):
        map_outline.main([str(src), "--solid-layer", "walls", "--json", str(src)])


def test_obj_drop_unused(tmp_path):
    src = tmp_path / "a.obj"
    src.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 9 9 9\n"
        "vt 0 0\nvt 1 0\nvt 0 1\nvt 0.5 0.5\n"
        "vn 0 0 1\nvn 0 1 0\n"
        "f 1/1/1 2/2/1 3/3/1\n"
    )
    out = tmp_path / "b.obj"
    assert obj_drop_unused.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["v"]["dropped"] == 1 and rec["vt"]["dropped"] == 1 and rec["vn"]["dropped"] == 1
    text = out.read_text()
    assert "v 9" not in text
    assert text.count("\nv ") + (1 if text.startswith("v ") else 0) == 3 or text.count("v ") == 3
    with pytest.raises(SystemExit):
        obj_drop_unused.main([str(src), "-o", str(src)])


def test_wav_limit(tmp_path):
    sr = 8000
    x = np.zeros(4000, dtype=np.float32)
    x[1000:2000] = 0.99  # nearly full scale
    src = _wav(tmp_path / "a.wav", x, sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 10, 3000))
    out = tmp_path / "l.wav"
    assert wav_limit.main([str(src), "-o", str(out), "--ceiling-db", "-6",
                           "--attack-ms", "0.5", "--release-ms", "1",
                           "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["peak"] <= 10 ** (-6 / 20) + 1e-3
    y, _ = audio_tidy.read_wav(str(out))
    assert len(y) == len(x)
    assert float(np.max(np.abs(y))) <= 10 ** (-6 / 20) + 1e-3
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 10 and loops[0]["end"] == 3000
    with pytest.raises(SystemExit):
        wav_limit.main([str(src), "-o", str(src)])


def test_sprite_align(tmp_path):
    # two red boxes of different sizes, both already in the corner — feet align should share a canvas
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    Image.new("RGBA", (4, 8), (0, 0, 0, 0)).paste(Image.new("RGBA", (4, 4), (255, 0, 0, 255)), (0, 4)) or None
    im_a = Image.new("RGBA", (4, 8), (0, 0, 0, 0))
    im_a.paste(Image.new("RGBA", (4, 4), (255, 0, 0, 255)), (0, 4))
    im_a.save(a)
    im_b = Image.new("RGBA", (8, 4), (255, 0, 0, 255))
    im_b.save(b)
    dest = tmp_path / "aligned"
    assert sprite_align.main([str(a), str(b), "-o", str(dest), "--anchor", "feet",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    wa = Image.open(dest / "a.png")
    wb = Image.open(dest / "b.png")
    assert wa.size == wb.size == tuple(rec["canvas"])
    # opaque bboxes are 4x4 and 8x4; feet sit on the same bottom row
    assert rec["canvas"][0] >= 8 and rec["canvas"][1] >= 4
    # feet of both red boxes should sit on the same bottom row
    def last_row(im):
        for y in range(im.size[1] - 1, -1, -1):
            for x in range(im.size[0]):
                if im.getpixel((x, y))[3] > 0:
                    return y
        return None
    assert last_row(wa) == last_row(wb)
    with pytest.raises(SystemExit):
        sprite_align.main([str(a), "-o", str(a), "--anchor", "feet"])


def test_glb_extras_strip(tmp_path):
    obj = tmp_path / "p.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path)]) == 0
    glb = tmp_path / "p.glb"
    gltf, bin_ = glb_lod.load_glb(str(glb))
    gltf["extras"] = {"note": "root"}
    gltf["meshes"][0]["extras"] = {"author": "kit"}
    dirty = tmp_path / "dirty.glb"
    glb_lod.save_glb(str(dirty), gltf, bin_)
    out = tmp_path / "clean.glb"
    assert glb_extras_strip.main([str(dirty), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["dropped"] >= 2
    cleaned, _ = glb_lod.load_glb(str(out))
    assert "extras" not in cleaned and "extras" not in cleaned["meshes"][0]
    with pytest.raises(SystemExit):
        glb_extras_strip.main([str(dirty), "-o", str(dirty)])


def test_tmx_tileset_list(tmp_path):
    src = tmp_path / "m.json"
    src.write_text(json.dumps({
        "type": "map", "width": 3, "height": 2, "tilewidth": 8, "tileheight": 8,
        "tilesets": [
            {"name": "ground", "firstgid": 1, "tilecount": 4, "columns": 2, "image": "g.png"},
            {"name": "unused", "firstgid": 10, "tilecount": 2, "columns": 2, "image": "u.png"},
        ],
        "layers": [{"type": "tilelayer", "name": "ground", "width": 3, "height": 2,
                    "data": [1, 2, 0, 1, 0, 0]}],
    }))
    assert tmx_tileset_list.main([str(src), "--json", str(tmp_path / "t.json"),
                                  "-o", str(tmp_path / "t.csv")]) == 0
    rec = json.load(open(tmp_path / "t.json"))
    assert rec["count"] == 2
    by = {t["name"]: t for t in rec["tilesets"]}
    assert by["ground"]["used_local_ids"] == 2 and by["unused"]["used_local_ids"] == 0
    empty = tmp_path / "e.json"
    empty.write_text(json.dumps({
        "type": "map", "width": 1, "height": 1, "tilewidth": 8, "tileheight": 8,
        "tilesets": [], "layers": [{"type": "tilelayer", "name": "g", "width": 1, "height": 1, "data": [0]}],
    }))
    assert tmx_tileset_list.main([str(empty), "--json", str(tmp_path / "e2.json"),
                                  "--fail-if-none"]) == 1
    with pytest.raises(SystemExit):
        tmx_tileset_list.main([str(src), "--json", str(src)])


def test_atlas_merge(tmp_path):
    s1 = Image.new("RGBA", (4, 2), (0, 0, 0, 0))
    s1.paste(Image.new("RGBA", (2, 2), (255, 0, 0, 255)), (0, 0))
    s1.paste(Image.new("RGBA", (2, 2), (0, 255, 0, 255)), (2, 0))
    a1 = _atlas(tmp_path / "a.json", "a.png",
                {"walk_01": (0, 0, 2, 2), "walk_02": (2, 0, 2, 2)}, (4, 2), s1)
    s2 = Image.new("RGBA", (2, 2), (0, 0, 255, 255))
    a2 = _atlas(tmp_path / "b.json", "b.png", {"coin": (0, 0, 2, 2)}, (2, 2), s2)
    dest = tmp_path / "merged"
    dest.mkdir()
    assert atlas_merge.main([str(a1), str(a2), "-o", str(dest / "all"), "--no-pot",
                             "--padding", "0", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["count"] == 3
    data, items, kind = atlas_json.load(str(dest / "all.json"))
    names = [n for n, _ in items]
    assert set(names) == {"walk_01", "walk_02", "coin"}
    # collision refused
    with pytest.raises(SystemExit):
        atlas_merge.main([str(a1), str(a1), "-o", str(tmp_path / "dup")])
    # prefix avoids collision
    assert atlas_merge.main([str(a1), str(a1), "-o", str(tmp_path / "pref"),
                             "--prefix", "a_,b_", "--no-pot", "--padding", "0"]) == 0
    _, items2, _ = atlas_json.load(str(tmp_path / "pref.json"))
    assert "a_walk_01" in dict(items2) and "b_walk_01" in dict(items2)
    with pytest.raises(SystemExit):
        atlas_merge.main([str(a1), str(a2), "-o", str(a1)])
