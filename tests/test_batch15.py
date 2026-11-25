import json, os, struct, wave
import numpy as np
import pytest
from PIL import Image
import audio_tidy, wav_loud_apply, anim_retarget_fps, credits_roll, map_stamp, obj_weld, tmx_objects_csv, jump_arc, texture_resize, map_diff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
DEJA = os.path.join(SAMPLES, "b9", "DejaVuSans-subset.ttf")


def tmap(layers, **kw):
    m = {"type": "map", "width": 4, "height": 2, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal",
         "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4, "image": "tileset.png", "tilewidth": 16, "tileheight": 16, "columns": 4}],
         "layers": layers}
    m.update(kw); return m


def write_wav(path, samples, sr=8000):
    x = np.asarray(samples, np.float32)
    if x.ndim == 1: x = x[:, None]
    audio_tidy.write_wav(str(path), x, sr, bits=16)


def test_wav_loud_apply(tmp_path):
    sr = 48000
    # 0.6s of a mid-level sine so LUFS is measurable (not SHORT)
    t = np.arange(int(0.6 * sr)) / sr
    x = 0.1 * np.sin(2 * np.pi * 1000 * t)
    src = tmp_path / "tone.wav"; write_wav(src, x, sr)
    assert wav_loud_apply.main([str(src), "--outdir", str(tmp_path / "out"), "--target", "-20", "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))[0]
    assert rec["out_lufs"] is not None and rec["lufs"] is not None
    # should be closer to -20 than the source was (allow a couple of LU of meter / peak-cap slack)
    assert abs(rec["out_lufs"] - (-20)) < 3
    with pytest.raises(SystemExit): wav_loud_apply.main([str(src)])


def test_anim_retarget_fps(tmp_path):
    clips = {"clips": [{"name": "walk", "fps": 10, "frames": [{"duration": 100}, {"duration": 100}, {"duration": 100}, {"duration": 100}]}]}
    json.dump(clips, open(tmp_path / "in.json", "w"))
    assert anim_retarget_fps.main([str(tmp_path / "in.json"), "-o", str(tmp_path / "out.json"), "--fps", "12",
                                   "--json-report", str(tmp_path / "r.json")]) == 0
    out = json.load(open(tmp_path / "out.json"))
    durs = [f["duration"] for f in out["clips"][0]["frames"]]
    assert out["clips"][0]["fps"] == 12 and abs(sum(durs) - 400) <= 1000 / 12 + 1
    assert all(d > 0 for d in durs)
    with pytest.raises(SystemExit): anim_retarget_fps.main([str(tmp_path / "in.json"), "-o", str(tmp_path / "in.json"), "--fps", "12"])


def test_credits_roll(tmp_path):
    (tmp_path / "c.txt").write_text("# CAST\nHero\nVillain\n\n# CREW\nDirector\n", encoding="utf-8")
    args = ["-o", str(tmp_path / "c.gif"), "--width", "160", "--height", "90", "--fps", "8", "--speed", "80",
            "--png", str(tmp_path / "c.png")]
    if os.path.isfile(DEJA): args += ["--font", DEJA]
    assert credits_roll.main([str(tmp_path / "c.txt")] + args) == 0
    im = Image.open(tmp_path / "c.gif")
    assert im.size == (160, 90) and getattr(im, "n_frames", 1) >= 2
    assert Image.open(tmp_path / "c.png").size == (160, 90)


def test_map_stamp_and_objects_csv(tmp_path):
    sheet = Image.new("RGBA", (64, 16), (255, 0, 0, 255)); sheet.save(tmp_path / "tileset.png")
    target = tmap([{"type": "tilelayer", "name": "base", "width": 4, "height": 2, "data": [1, 0, 0, 0, 0, 0, 0, 0]},
                   {"type": "objectgroup", "name": "obj", "objects": [{"id": 1, "name": "old", "type": "npc", "x": 0, "y": 0}]}])
    prefab = tmap([{"type": "tilelayer", "name": "p", "width": 2, "height": 1, "data": [2, 3]},
                   {"type": "objectgroup", "name": "obj", "objects": [{"id": 1, "name": "chest", "type": "pickup", "x": 0, "y": 0,
                                                                      "properties": [{"name": "gold", "value": 5}]}]}],
                  width=2, height=1)
    json.dump(target, open(tmp_path / "t.json", "w")); json.dump(prefab, open(tmp_path / "p.json", "w"))
    assert map_stamp.main([str(tmp_path / "t.json"), "--prefab", str(tmp_path / "p.json"), "-o", str(tmp_path / "stamped.json"),
                           "--at", "1,0", "--layer", "base", "--object-layer", "obj", "--prefix", "pf_"]) == 0
    m = json.load(open(tmp_path / "stamped.json"))
    base = next(l for l in m["layers"] if l["name"] == "base")
    assert base["data"][1] == 2 and base["data"][2] == 3 and base["data"][0] == 1
    objs = next(l for l in m["layers"] if l["name"] == "obj")["objects"]
    names = [o["name"] for o in objs]
    assert "old" in names and "pf_chest" in names
    # export / import objects
    assert tmx_objects_csv.main([str(tmp_path / "stamped.json"), "-o", str(tmp_path / "objs.csv")]) == 0
    text = open(tmp_path / "objs.csv").read()
    assert "pf_chest" in text and "gold" in text
    # bump gold and add a row
    lines = text.strip().splitlines(); header = lines[0].split(",")
    # rewrite chest gold
    new = []
    for line in lines:
        if "pf_chest" in line: line = line.replace(",5", ",9") if ",5" in line else line
        new.append(line)
    # add a new object (blank id)
    # build via the tool's import after editing csv
    import csv as csvmod
    rows = list(csvmod.DictReader(open(tmp_path / "objs.csv")))
    for r in rows:
        if r["name"] == "pf_chest": r["gold"] = "9"
    rows.append({"map": "stamped.json", "layer": "obj", "id": "", "name": "newone", "type": "marker", "x": "16", "y": "16",
                 "width": "0", "height": "0", "rotation": "0", "gid": "", "visible": "true", "gold": ""})
    with open(tmp_path / "edit.csv", "w", newline="") as fh:
        w = csvmod.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    assert tmx_objects_csv.main([str(tmp_path / "stamped.json"), "--import-csv", str(tmp_path / "edit.csv"),
                                 "-o", str(tmp_path / "applied.json")]) == 0
    applied = json.load(open(tmp_path / "applied.json"))
    objs = next(l for l in applied["layers"] if l["name"] == "obj")["objects"]
    chest = next(o for o in objs if o["name"] == "pf_chest")
    assert map_diff.props(chest).get("gold") in (9, "9")
    assert any(o["name"] == "newone" for o in objs)


def test_obj_weld(tmp_path):
    # two cubes sharing a plane: 8+8 verts with 4 exact duplicates along the weld
    # simpler: a triangle with a repeated vertex and a nearly-coincident one
    obj = """v 0 0 0
v 1 0 0
v 0 1 0
v 0.0000004 0 0
f 1 2 3
f 4 2 3
"""
    (tmp_path / "a.obj").write_text(obj)
    assert obj_weld.main([str(tmp_path / "a.obj"), "-o", str(tmp_path / "w.obj"), "--epsilon", "1e-5", "--json", str(tmp_path / "w.json")]) == 0
    rec = json.load(open(tmp_path / "w.json"))
    assert rec["vertices_before"] == 4 and rec["vertices_after"] == 3
    text = open(tmp_path / "w.obj").read()
    assert text.count("\nv ") + (1 if text.startswith("v ") else 0) == 3 or text.splitlines() and sum(1 for l in text.splitlines() if l.startswith("v ")) == 3
    # OBJ relative (negative) indices
    (tmp_path / "rel.obj").write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n")
    assert obj_weld.main([str(tmp_path / "rel.obj"), "-o", str(tmp_path / "relw.obj")]) == 0
    assert sum(1 for l in open(tmp_path / "relw.obj") if l.startswith("v ")) == 3
    with pytest.raises(SystemExit): obj_weld.main([str(tmp_path / "a.obj"), "-o", str(tmp_path / "a.obj")])


def test_jump_arc_and_resize(tmp_path):
    assert jump_arc.main(["-o", str(tmp_path / "arc.png"), "--width", "200", "--height", "120",
                          "--start", "20,100", "--jump-v", "180", "--speed", "80", "--gravity", "600",
                          "--json", str(tmp_path / "arc.json")]) == 0
    im = Image.open(tmp_path / "arc.png"); assert im.size == (200, 120)
    rec = json.load(open(tmp_path / "arc.json"))
    assert rec["points"] > 5 and rec["range_px"] > 10 and rec["apex"][1] < 100
    # over a real map if present
    cave = os.path.join(SAMPLES, "b11", "cave_obj.json")
    tiles = os.path.join(SAMPLES, "tileset.png")
    if os.path.isfile(cave):
        args = [cave, "-o", str(tmp_path / "cave_arc.png"), "--start", "32,32", "--scale", "1"]
        if os.path.isfile(tiles): args += ["--tileset", tiles]
        assert jump_arc.main(args) == 0
        assert Image.open(tmp_path / "cave_arc.png").size[0] > 16
    # texture resize
    im = Image.new("RGB", (100, 60), (10, 20, 30)); im.save(tmp_path / "t.png")
    assert texture_resize.main([str(tmp_path / "t.png"), "-o", str(tmp_path / "resized"), "--max", "50",
                                "--json", str(tmp_path / "rs.json")]) == 0
    out = Image.open(tmp_path / "resized" / "t.png")
    assert max(out.size) == 50
    Image.new("RGB", (100, 60), (1, 2, 3)).save(tmp_path / "p.png")
    assert texture_resize.main([str(tmp_path / "p.png"), "-o", str(tmp_path / "pot"), "--pot"]) == 0
    pw, ph = Image.open(tmp_path / "pot" / "p.png").size
    assert pw & (pw - 1) == 0 and ph & (ph - 1) == 0 and pw <= 100 and ph <= 60
