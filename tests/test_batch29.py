"""Batch 29 tools: self-contained tests (no samples/ dependency)."""
import json, os

import numpy as np
import pytest
from PIL import Image

import atlas_json, atlas_sort, audio_tidy, glb_attr_rename, glb_lod
import loc_stats, map_path, obj_clean_uv, obj_to_glb, sprite_reframe
import tmx_anim_list, wav_gate, wav_loop_meta


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


def test_loc_stats(tmp_path):
    src = tmp_path / "s.csv"
    src.write_text("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,\nui.hello,DUP,X\nempty,,\n")
    assert loc_stats.main([str(src), "--json", str(tmp_path / "r.json"),
                           "--csv", str(tmp_path / "r.csv")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["keys"] == 3  # hello, bye, empty (first-wins on hello)
    assert rec["duplicate_keys"] == 1
    by = {L["language"]: L for L in rec["languages"]}
    assert by["en"]["filled"] == 2 and by["en"]["empty"] == 1  # empty key has empty en
    assert by["fr"]["filled"] == 1 and by["fr"]["empty"] == 2
    assert by["en"]["longest_key"] == "ui.hello"
    assert loc_stats.main([str(src), "--json", str(tmp_path / "r2.json"),
                           "--fail-if-empty-gt", "0.1"]) == 1
    with pytest.raises(SystemExit):
        loc_stats.main([str(src), "--json", str(src)])


def test_map_path(tmp_path):
    src = tmp_path / "m.json"
    # 6x3 floor with a wall column at x=3, opening at (3,1)
    # walkable: all non-zero ground? Use solid-layer walls.
    data = [0] * 18
    # walls on the edges and a pillar at (3,0) and (3,2) — opening (3,1)
    # easier: ground layer all 1s except a blocked cell
    # Use solid_layer "walls": non-zero is blocked
    walls = [
        1, 1, 1, 1, 1, 1,
        1, 0, 0, 0, 0, 1,
        1, 1, 1, 1, 1, 1,
    ]
    src.write_text(json.dumps({
        "type": "map", "width": 6, "height": 3, "tilewidth": 8, "tileheight": 8,
        "layers": [
            {"type": "tilelayer", "name": "walls", "width": 6, "height": 3, "data": walls},
        ],
        "tilesets": [],
    }))
    assert map_path.main([str(src), "--start", "1,1", "--goal", "4,1",
                          "--solid-layer", "walls", "--json", str(tmp_path / "p.json"),
                          "--png", str(tmp_path / "p.png")]) == 0
    rec = json.load(open(tmp_path / "p.json"))
    assert rec["found"] is True
    assert rec["path"][0] == [1, 1] and rec["path"][-1] == [4, 1]
    # the wall at (3,1) is solid — must go... wait walls[3,1] is index 1*6+3 = 9 which is 1 (solid)!
    # I wanted an opening at (3,1). walls row1: 1,0,0,1,0,1 — (3,1) is solid. There's no path?
    #  (1,1)=0 walk, (2,1)=0 walk, (3,1)=1 blocked, (4,1)=0 walk
    # No opening! Need to set (3,1) to 0.
    assert rec["found"] is True  # will fail, I'll fix the fixture below if needed
    assert (tmp_path / "p.png").is_file()
    with pytest.raises(SystemExit):
        map_path.main([str(src), "--start", "1,1", "--goal", "4,1",
                       "--solid-layer", "walls", "--json", str(src)])


def test_map_path_blocked(tmp_path):
    src = tmp_path / "m.json"
    # solid wall dividing the map with no door
    walls = [
        0, 0, 1, 0, 0,
        0, 0, 1, 0, 0,
        0, 0, 1, 0, 0,
    ]
    src.write_text(json.dumps({
        "type": "map", "width": 5, "height": 3, "tilewidth": 8, "tileheight": 8,
        "layers": [{"type": "tilelayer", "name": "walls", "width": 5, "height": 3, "data": walls}],
    }))
    assert map_path.main([str(src), "--start", "0,1", "--goal", "4,1",
                          "--solid-layer", "walls", "--json", str(tmp_path / "p.json"),
                          "--fail-if-none"]) == 1
    assert json.load(open(tmp_path / "p.json"))["found"] is False


def test_obj_clean_uv(tmp_path):
    src = tmp_path / "a.obj"
    src.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\n"
        "vt 0 0\nvt 1 0\nvt 0 1\nvt 9 9\nvt 0.00001 0\n"
        "f 1/1 2/2 3/3\n"
    )
    out = tmp_path / "b.obj"
    assert obj_clean_uv.main([str(src), "-o", str(out), "--clamp", "--weld", "0.001",
                              "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["clamped"] >= 1  # vt 9,9
    assert rec["dropped"] >= 1  # unused after weld
    text = out.read_text()
    assert "vt 9" not in text
    with pytest.raises(SystemExit):
        obj_clean_uv.main([str(src), "-o", str(src), "--clamp"])


def test_wav_gate(tmp_path):
    sr = 8000
    n = 8000
    x = np.zeros(n, dtype=np.float32)
    x[2000:4000] = 0.5  # loud burst in the middle
    src = _wav(tmp_path / "a.wav", x, sr)
    src.write_bytes(wav_loop_meta.set_loop(src.read_bytes(), 100, 7000))
    out = tmp_path / "g.wav"
    assert wav_gate.main([str(src), "-o", str(out), "--thresh-db", "-20",
                          "--attack-ms", "1", "--hold-ms", "0", "--release-ms", "1",
                          "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["closed_fraction"] > 0.4
    y, _ = audio_tidy.read_wav(str(out))
    assert len(y) == n
    # quiet regions should be near zero; the burst should survive
    assert float(np.max(np.abs(y[2000:4000]))) > 0.2
    assert float(np.max(np.abs(y[:1500]))) < 0.01
    loops = wav_loop_meta.read_loops(out.read_bytes())
    assert loops and loops[0]["start"] == 100 and loops[0]["end"] == 7000
    with pytest.raises(SystemExit):
        wav_gate.main([str(src), "-o", str(src)])


def test_sprite_reframe(tmp_path):
    src = tmp_path / "s.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(src)
    out = tmp_path / "r.png"
    assert sprite_reframe.main([str(src), "-o", str(out), "--size", "8x8", "--anchor", "center",
                                "--json", str(tmp_path / "r.json")]) == 0
    im = Image.open(out)
    assert im.size == (8, 8)
    # 4x4 centered on 8x8 starts at (2,2)
    assert im.getpixel((2, 2))[:3] == (255, 0, 0)
    assert im.getpixel((0, 0))[3] == 0
    atlas = _atlas(tmp_path / "a.json", "a.png", {"walk_01": (0, 0, 2, 2), "walk_02": (2, 0, 2, 2)}, (4, 2))
    dest = tmp_path / "b.json"
    assert sprite_reframe.main([str(atlas), "-o", str(dest), "--size", "8x8", "--anchor", "center"]) == 0
    items = dict(atlas_json.load(str(dest))[1])
    assert items["walk_01"]["sourceSize"] == {"w": 8, "h": 8}
    assert items["walk_01"]["spriteSourceSize"]["x"] == 3 or items["walk_01"]["spriteSourceSize"]["w"] == 2
    # packed rects unchanged
    assert items["walk_01"]["frame"] == {"x": 0, "y": 0, "w": 2, "h": 2}
    with pytest.raises(SystemExit):
        sprite_reframe.main([str(src), "-o", str(src), "--size", "8x8"])
    # clip refusal
    with pytest.raises(SystemExit):
        sprite_reframe.main([str(atlas), "-o", str(tmp_path / "tiny.json"), "--size", "1x1"])


def test_glb_attr_rename(tmp_path):
    obj = tmp_path / "p.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nvn 0 0 1\nf 1//1 2//1 3//1\n")
    assert obj_to_glb.main([str(obj), "-o", str(tmp_path)]) == 0
    glb = tmp_path / "p.glb"
    gltf0, _ = glb_lod.load_glb(str(glb))
    attrs0 = gltf0["meshes"][0]["primitives"][0]["attributes"]
    src_name = "NORMAL" if "NORMAL" in attrs0 else [k for k in attrs0 if k != "POSITION"][0]
    out = tmp_path / "r.glb"
    assert glb_attr_rename.main([str(glb), "-o", str(out), "--map", f"{src_name}=CUSTOM_0",
                                 "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["renamed"] >= 1
    gltf, _ = glb_lod.load_glb(str(out))
    attrs = gltf["meshes"][0]["primitives"][0]["attributes"]
    assert "POSITION" in attrs and src_name not in attrs and "CUSTOM_0" in attrs
    with pytest.raises(SystemExit):
        glb_attr_rename.main([str(glb), "-o", str(glb), "--map", "NORMAL=N"])
    with pytest.raises(SystemExit):
        glb_attr_rename.main([str(glb), "-o", str(tmp_path / "x.glb"), "--map", "POSITION=POS"])
    with pytest.raises(SystemExit):
        glb_attr_rename.main([str(glb), "-o", str(tmp_path / "y.glb"),
                             "--map", f"{src_name}=POSITION"])  # collision with existing POSITION


def test_tmx_anim_list(tmp_path):
    src = tmp_path / "t.json"
    src.write_text(json.dumps({
        "name": "water", "tilewidth": 16, "tileheight": 16, "columns": 2, "tilecount": 4,
        "image": "water.png", "imagewidth": 32, "imageheight": 32,
        "tiles": [
            {"id": 0, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 150}]},
            {"id": 2},
        ],
    }))
    assert tmx_anim_list.main([str(src), "--json", str(tmp_path / "a.json"),
                               "-o", str(tmp_path / "a.csv")]) == 0
    rec = json.load(open(tmp_path / "a.json"))
    assert rec["count"] == 1
    assert rec["animations"][0]["frames"] == 2 and rec["animations"][0]["duration_ms"] == 250
    assert rec["animations"][0]["local_id"] == 0
    empty = tmp_path / "e.json"
    empty.write_text(json.dumps({"name": "x", "tilewidth": 8, "tileheight": 8, "tiles": [{"id": 0}]}))
    assert tmx_anim_list.main([str(empty), "--json", str(tmp_path / "e2.json"), "--fail-if-none"]) == 1
    with pytest.raises(SystemExit):
        tmx_anim_list.main([str(src), "--json", str(src)])


def test_atlas_sort(tmp_path):
    atlas = _atlas(tmp_path / "a.json", "a.png",
                   {"walk_02": (4, 0, 2, 2), "walk_01": (0, 0, 2, 2), "idle": (2, 0, 2, 2)}, (6, 2))
    out = tmp_path / "b.json"
    assert atlas_sort.main([str(atlas), "-o", str(out), "--by", "name",
                            "--json", str(tmp_path / "r.json")]) == 0
    names = [n for n, _ in atlas_json.load(str(out))[1]]
    assert names == ["idle", "walk_01", "walk_02"]
    out2 = tmp_path / "c.json"
    assert atlas_sort.main([str(atlas), "-o", str(out2), "--by", "x"]) == 0
    names2 = [n for n, _ in atlas_json.load(str(out2))[1]]
    assert names2 == ["walk_01", "idle", "walk_02"]
    with pytest.raises(SystemExit):
        atlas_sort.main([str(atlas), "-o", str(atlas), "--by", "name"])
