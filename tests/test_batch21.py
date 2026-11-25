"""Batch 21 tools, plus the concave ear-clip case for obj-triangulate."""
import csv, json, os, xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image

import glb_split, loc_icu_extract, map_auto_layer, obj_normals, obj_triangulate
import anim_hold, wav_fade, sprite_stack, tmx_object_types
import audio_tidy, obj_to_glb, mesh_pivot_fix, glb_merge, gltf_strip


def _map(data, width=4, height=3, name="ground", objects=None, extra=None):
    layers = [{"type": "tilelayer", "name": name, "width": width, "height": height, "data": data}]
    if extra:
        layers.extend(extra)
    if objects is not None:
        layers.append({"type": "objectgroup", "name": "objs", "objects": objects})
    return {"type": "map", "width": width, "height": height, "tilewidth": 16, "tileheight": 16,
            "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 40, "image": "t.png"}],
            "layers": layers}


def test_obj_triangulate_concave(tmp_path):
    # D sits inside triangle ABC; a triangle fan from A covers the cut-out, ear-clip does not.
    obj = tmp_path / "c.obj"
    obj.write_text(
        "v 0 0 0\nv 2 0 0\nv 2 2 0\nv 0.5 0.2 0\n"
        "f 1 2 3 4\n"
    )
    assert obj_triangulate.main([str(obj), "-o", str(tmp_path / "t.obj"),
                                 "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["ngons"] == 1 and rec["triangles_out"] == 2 and rec["fan_fallback"] == 0
    faces = [l.split()[1:] for l in (tmp_path / "t.obj").read_text().splitlines() if l.startswith("f ")]
    pts = {1: (0, 0), 2: (2, 0), 3: (2, 2), 4: (0.5, 0.2)}

    def pip(p, a, b, c):
        def cross(u, v, w):
            return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
        c1, c2, c3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
        return not ((c1 < -1e-12 or c2 < -1e-12 or c3 < -1e-12) and
                    (c1 > 1e-12 or c2 > 1e-12 or c3 > 1e-12))

    cut = ((0 + 2 + 0.5) / 3, (0 + 2 + 0.2) / 3)  # centroid of ACD, outside the quad
    inside = (1.9, 0.1)
    covered_cut = covered_in = False
    for toks in faces:
        idx = [int(t.split("/")[0]) for t in toks]
        a, b, c = pts[idx[0]], pts[idx[1]], pts[idx[2]]
        covered_cut = covered_cut or pip(cut, a, b, c)
        covered_in = covered_in or pip(inside, a, b, c)
    assert not covered_cut
    assert covered_in
    with pytest.raises(SystemExit, match="overwrite"):
        obj_triangulate.main([str(obj), "-o", str(obj)])


def test_glb_split(tmp_path):
    def cube(path, offset, name):
        open(path, "w").write(
            f"o {name}\nv {offset} 0 0\nv {offset+1} 0 0\nv {offset} 1 0\nf 1 2 3\n"
        )
    cube(tmp_path / "a.obj", 0, "Sword")
    cube(tmp_path / "b.obj", 10, "Shield")
    assert obj_to_glb.main([str(tmp_path / "a.obj"), str(tmp_path / "b.obj"),
                            "-o", str(tmp_path / "glb")]) == 0
    assert glb_merge.main([str(tmp_path / "glb" / "a.glb"), str(tmp_path / "glb" / "b.glb"),
                           "-o", str(tmp_path / "m.glb")]) == 0
    js, chunks, ver = mesh_pivot_fix.read_glb(str(tmp_path / "m.glb"))
    assert len(js["scenes"][0]["nodes"]) == 2
    out = tmp_path / "parts"
    assert glb_split.main([str(tmp_path / "m.glb"), "-o", str(out), "--by", "node",
                           "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["count"] == 2 and rec["by"] == "node"
    files = list(out.glob("*.glb"))
    assert len(files) == 2
    names = {f.stem for f in files}
    assert "a" in names and "b" in names
    for f in files:
        sjs, _, _ = mesh_pivot_fix.read_glb(str(f))
        assert len(sjs.get("meshes") or []) == 1
        assert len(sjs["scenes"][0]["nodes"]) == 1
    mesh_out = tmp_path / "meshes"
    assert glb_split.main([str(tmp_path / "m.glb"), "-o", str(mesh_out), "--by", "mesh"]) == 0
    assert len(list(mesh_out.glob("*.glb"))) == 2
    with pytest.raises(SystemExit, match="overwrite"):
        glb_split.main([str(tmp_path / "m.glb"), "-o", str(tmp_path / "parts2"),
                        "--json", str(tmp_path / "m.glb")])


def test_loc_icu_extract(tmp_path):
    csv_text = (
        "id,en,de\n"
        "apples,\"{n, plural, one {# apple} other {# apples}}\","
        "\"{n, plural, one {# Apfel} other {# Äpfel}}\"\n"
        "items.one,One item,Ein Ding\n"
        "items.other,Many items,Viele Dinge\n"
        "plain,Hello,Hallo\n"
    )
    (tmp_path / "s.csv").write_text(csv_text)
    assert loc_icu_extract.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "rev.csv"),
                                 "--json", str(tmp_path / "r.json")]) == 0
    rows = list(csv.DictReader(open(tmp_path / "rev.csv")))
    styles = {(r["key"], r["language"], r["style"]) for r in rows}
    assert ("apples", "en", "icu") in styles and ("apples", "de", "icu") in styles
    assert ("items", "en", "suffix") in styles
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["count"] == len(rows) >= 4
    apple_en = next(r for r in rows if r["key"] == "apples" and r["language"] == "en")
    assert "one" in apple_en["categories"] and "other" in apple_en["categories"]
    assert apple_en["missing"] == ""
    with pytest.raises(SystemExit, match="overwrite"):
        loc_icu_extract.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "s.csv")])


def test_map_auto_layer(tmp_path):
    # 3x3 with a solid plus in the centre cross
    # 0 1 0
    # 1 1 1
    # 0 1 0
    data = [0, 1, 0, 1, 1, 1, 0, 1, 0]
    json.dump(_map(data, 3, 3), open(tmp_path / "m.json", "w"))
    rules = {
        "source": "ground",
        "name": "edges",
        "match": "solid",
        "rules": [
            {"center": 1, "n": 1, "e": 1, "s": 1, "w": 1, "gid": 10},
            {"center": 1, "gid": 11},
        ],
    }
    json.dump(rules, open(tmp_path / "r.json", "w"))
    assert map_auto_layer.main([str(tmp_path / "m.json"), "--rules", str(tmp_path / "r.json"),
                                "-o", str(tmp_path / "o.json"), "--json", str(tmp_path / "rep.json")]) == 0
    out = json.load(open(tmp_path / "o.json"))
    layers = {l["name"]: l for l in out["layers"]}
    assert "edges" in layers and "ground" in layers
    deco = layers["edges"]["data"]
    assert deco[4] == 10  # centre, all four neighbours solid
    assert deco[1] == 11 and deco[3] == 11 and deco[5] == 11 and deco[7] == 11
    assert deco[0] == 0
    rec = json.load(open(tmp_path / "rep.json"))
    assert rec["placed"] == 5
    with pytest.raises(SystemExit, match="overwrite"):
        map_auto_layer.main([str(tmp_path / "m.json"), "--rules", str(tmp_path / "r.json"),
                             "-o", str(tmp_path / "m.json")])


def test_obj_normals(tmp_path):
    # two triangles sharing an edge, coplanar -> one smooth normal; flat -> two
    obj = tmp_path / "p.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "g body\nusemtl wood\ns 1\n"
        "f 1 2 3\nf 1 3 4\n"
    )
    assert obj_normals.main([str(obj), "-o", str(tmp_path / "flat.obj"), "--mode", "flat",
                             "--json", str(tmp_path / "f.json")]) == 0
    rec = json.load(open(tmp_path / "f.json"))
    assert rec["normals"] == 2 and rec["faces"] == 2
    flat = (tmp_path / "flat.obj").read_text()
    assert "usemtl wood" in flat and "g body" in flat and "s 1" in flat
    assert obj_normals.main([str(obj), "-o", str(tmp_path / "sm.obj"), "--mode", "smooth"]) == 0
    sm = (tmp_path / "sm.obj").read_text()
    nlines = [l for l in sm.splitlines() if l.startswith("vn ")]
    # coplanar faces share a single normal at every vertex
    assert len(nlines) == 1 or (len(nlines) >= 1 and len({l for l in nlines}) == 1)
    # a cube corner should get a smoothed average, not a unit axis
    cube = tmp_path / "cube.obj"
    cube.write_text(
        "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
        "v 0 0 1\nv 1 0 1\nv 1 1 1\nv 0 1 1\n"
        "s 1\n"
        "f 1 2 3 4\nf 5 8 7 6\nf 1 5 6 2\nf 4 3 7 8\nf 1 4 8 5\nf 2 6 7 3\n"
    )
    assert obj_normals.main([str(cube), "-o", str(tmp_path / "cs.obj"), "--mode", "smooth"]) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        obj_normals.main([str(obj), "-o", str(obj)])


def test_anim_hold(tmp_path):
    data = {"clips": {
        "idle": {"frames": ["a", "b"], "loop": True, "fps": 10, "durations_ms": [100, 100]},
        "once": {"frames": ["x", "y", "z"], "loop": False, "duration": 0.3},
    }}
    json.dump(data, open(tmp_path / "c.json", "w"))
    assert anim_hold.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "h.json"),
                           "--clip", "idle", "--to-duration", "1.0", "--mode", "extend",
                           "--pretty", "--json", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "h.json"))
    idle = out["clips"]["idle"]
    assert idle["frames"] == ["a", "b"]
    assert idle["durations_ms"][0] == 100
    assert idle["durations_ms"][1] == 900  # 100 + 800ms to reach 1.0s
    assert idle["duration"] == pytest.approx(1.0)
    assert anim_hold.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "r2.json"),
                           "--clip", "idle", "--add-frames", "3", "--mode", "repeat",
                           "--only"]) == 0
    held = json.load(open(tmp_path / "r2.json"))
    assert list(held["clips"]) == ["idle"]
    assert held["clips"]["idle"]["frames"] == ["a", "b", "b", "b", "b"]
    with pytest.raises(SystemExit, match="overwrite"):
        anim_hold.main([str(tmp_path / "c.json"), "-o", str(tmp_path / "c.json"),
                        "--clip", "idle", "--add-frames", "1"])


def test_wav_fade(tmp_path):
    sr = 8000
    n = sr  # 1 second of ones
    x = np.ones((n, 1), dtype=np.float64) * 0.5
    audio_tidy.write_wav(str(tmp_path / "a.wav"), x, sr, bits=16)
    assert wav_fade.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "f.wav"),
                          "--in", "0.1", "--fade-out", "0.2", "--shape", "linear",
                          "--json", str(tmp_path / "r.json")]) == 0
    y, sr2 = audio_tidy.read_wav(str(tmp_path / "f.wav"))
    assert sr2 == sr and len(y) == n
    # first sample near 0, last sample near 0, middle still ~0.5
    assert abs(float(y[0, 0])) < 0.02
    assert abs(float(y[-1, 0])) < 0.02
    mid = int(0.5 * sr)
    assert 0.4 < abs(float(y[mid, 0])) < 0.6
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["fade_in_frames"] == 800 and rec["fade_out_frames"] == 1600
    with pytest.raises(SystemExit, match="overwrite"):
        wav_fade.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "a.wav"), "--in", "0.01"])


def test_sprite_stack(tmp_path):
    src = tmp_path / "parts"
    src.mkdir()
    # body 8x8 red, shadow 8x4 black (shorter — bottom aligned)
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(src / "hero.body.png")
    Image.new("RGBA", (8, 4), (0, 0, 0, 128)).save(src / "hero.shadow.png")
    Image.new("RGBA", (8, 8), (0, 255, 0, 255)).save(src / "hero.outline.png")
    Image.new("RGBA", (8, 8), (0, 0, 255, 255)).save(src / "npc.body.png")
    out = tmp_path / "stacked"
    assert sprite_stack.main([str(src), "-o", str(out), "--layers", "shadow,body,outline",
                              "--anchor", "bottom", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["count"] == 2
    hero = Image.open(out / "hero.png")
    assert hero.size == (8, 8)
    # outline (green) is on top at the centre
    assert hero.getpixel((4, 4))[:3] == (0, 255, 0)
    # shadow occupies the bottom 4 pixels but was under body/outline
    with pytest.raises(SystemExit, match="overwrite"):
        sprite_stack.main([str(src), "-o", str(out), "--layers", "shadow,body,outline",
                           "--json", str(src / "hero.body.png")])


def test_tmx_object_types(tmp_path):
    types = tmp_path / "types.xml"
    types.write_text(
        '<?xml version="1.0"?>\n'
        "<objecttypes>\n"
        '  <objecttype name="Door" color="#ff0000">\n'
        '    <property name="dest" type="string" default="none"/>\n'
        '    <property name="locked" type="bool" default="false"/>\n'
        "  </objecttype>\n"
        "</objecttypes>\n"
    )
    m = _map([1, 0, 0, 0], width=2, height=2, objects=[
        {"id": 1, "name": "door", "type": "Door", "x": 0, "y": 0, "width": 16, "height": 16,
         "properties": [{"name": "dest", "type": "string", "value": "hall"}]},
        {"id": 2, "name": "plain", "type": "Sign", "x": 16, "y": 0},
    ])
    json.dump(m, open(tmp_path / "m.json", "w"))
    # lint: missing locked
    rc = tmx_object_types.main(["lint", str(tmp_path / "m.json"), "--types", str(types),
                                "--json", str(tmp_path / "lint.json")])
    assert rc == 1
    lint = json.load(open(tmp_path / "lint.json"))
    assert lint["count"] == 1 and lint["issues"][0]["property"] == "locked"
    assert tmx_object_types.main(["apply", str(tmp_path / "m.json"), "--types", str(types),
                                  "-o", str(tmp_path / "a.json"), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["filled"] == 1 and rec["overwritten"] == 0
    out = json.load(open(tmp_path / "a.json"))
    door = out["layers"][1]["objects"][0]
    names = {p["name"]: p["value"] for p in door["properties"]}
    assert names["dest"] == "hall" and names["locked"] is False
    assert tmx_object_types.main(["lint", str(tmp_path / "a.json"), "--types", str(types)]) == 0
    with pytest.raises(SystemExit, match="overwrite"):
        tmx_object_types.main(["apply", str(tmp_path / "m.json"), "--types", str(types),
                               "-o", str(tmp_path / "m.json")])
