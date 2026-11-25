import json, math, os, struct, wave
import numpy as np
import pytest
from PIL import Image
import sprite_sheet_optimize, gif_to_frames, tileset_from_image, map_diff, mesh_pivot_fix, voice_slate, wav_batch_meta, input_map_lint
import obj_to_glb, gltf_inspect, audio_tidy


# ---------- sprite-sheet-optimize
def make_sheet(tmp_path):
    """3 frames in a 64x32 sheet: A and B have identical pixels (different position), C differs. Source frames are 16x16 with padding."""
    sheet = Image.new("RGBA", (64, 32), (0, 0, 0, 0)); a = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for (x, y) in ((5, 3), (6, 3), (5, 4), (6, 4), (7, 6)): a.putpixel((x, y), (255, 0, 0, 255))
    c = Image.new("RGBA", (16, 16), (0, 0, 0, 0)); c.paste(Image.new("RGBA", (6, 3), (0, 0, 255, 255)), (2, 9))
    sheet.paste(a, (0, 0)); sheet.paste(a, (32, 16)); sheet.paste(c, (16, 0))
    meta = {"frames": {n: {"frame": {"x": x, "y": y, "w": 16, "h": 16}, "sourceSize": {"w": 16, "h": 16}, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16}} for n, (x, y) in
                       (("a", (0, 0)), ("c", (16, 0)), ("b", (32, 16)))}, "meta": {"image": "s.png"}}
    sheet.save(tmp_path / "s.png"); json.dump(meta, open(tmp_path / "s.json", "w")); return sheet, meta


def rebuild(im, e):
    f, s, src = e["frame"], e["spriteSourceSize"], e["sourceSize"]; canvas = Image.new("RGBA", (src["w"], src["h"]), (0, 0, 0, 0))
    canvas.paste(im.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"])), (s["x"], s["y"])); return np.array(canvas)


def test_sheet_optimize(tmp_path):
    sheet, meta = make_sheet(tmp_path)
    im, frames, st = sprite_sheet_optimize.optimize(sheet, meta)
    assert st["frames"] == 3 and st["unique"] == 2 and st["area_after"] < st["area_before"] / 4
    assert frames["b"].get("alias_of") == "a" and "alias_of" not in frames["a"] and frames["b"]["frame"] == frames["a"]["frame"]
    old = np.array(sheet)
    for n, e in meta["frames"].items():                                  # every frame reconstructs exactly, offsets included
        f = e["frame"]; want = old[f["y"]:f["y"] + 16, f["x"]:f["x"] + 16]
        assert (rebuild(im, frames[n]) == want).all(), n
    assert frames["a"]["spriteSourceSize"] == {"x": 5, "y": 3, "w": 3, "h": 4} and frames["a"]["trimmed"]
    narrow, _, _ = sprite_sheet_optimize.optimize(sheet, meta, max_width=8); assert narrow.width <= 8 and narrow.height >= 4 * 2
    with pytest.raises(SystemExit): sprite_sheet_optimize.optimize(sheet, meta, max_width=2)
    _, _, st2 = sprite_sheet_optimize.optimize(sheet, meta, dedupe_frames=False); assert st2["unique"] == 3
    im3, _, _ = sprite_sheet_optimize.optimize(sheet, meta, pot=True); assert im3.width & (im3.width - 1) == 0 and im3.height & (im3.height - 1) == 0
    # array layout + rotated refusal + empty frame
    arr = {"frames": [dict(v, filename=k) for k, v in meta["frames"].items()]}; assert sprite_sheet_optimize.optimize(sheet, arr)[2]["unique"] == 2
    bad = json.loads(json.dumps(meta)); bad["frames"]["a"]["rotated"] = True
    with pytest.raises(SystemExit): sprite_sheet_optimize.optimize(sheet, bad)
    empty = json.loads(json.dumps(meta)); empty["frames"]["e"] = {"frame": {"x": 48, "y": 0, "w": 16, "h": 16}, "sourceSize": {"w": 16, "h": 16}, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16}}
    _, fr, _ = sprite_sheet_optimize.optimize(sheet, empty); assert fr["e"]["frame"]["w"] == 1
    assert sprite_sheet_optimize.main([str(tmp_path / "s.json"), "-o", str(tmp_path / "o")]) == 0
    o = json.load(open(tmp_path / "o.json")); assert o["meta"]["image"] == "o.png" and Image.open(tmp_path / "o.png").size == tuple(o["meta"]["size"].values())


# ---------- gif-to-frames
def test_gif_to_frames(tmp_path):
    cols = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]; ims = [Image.new("RGB", (8, 6), c) for c in cols]
    ims[0].save(tmp_path / "a.gif", save_all=True, append_images=ims[1:], duration=[100, 150, 300], loop=0)
    assert gif_to_frames.main([str(tmp_path / "a.gif"), "-o", str(tmp_path / "f"), "--strip"]) == 0
    m = json.load(open(tmp_path / "f" / "frames.json")); assert [f["duration_ms"] for f in m["frames"]] == [100, 150, 300] and m["total_ms"] == 550 and m["size"] == [8, 6]
    im = Image.open(tmp_path / "f" / "frame_0001.png"); assert im.mode == "RGBA" and im.getpixel((3, 3))[:3] == (0, 255, 0)
    assert Image.open(tmp_path / "f" / "frame_strip.png").size == (24, 6)
    fr = [(Image.new("RGBA", (2, 2), (1, 2, 3, 255)), 40), (Image.new("RGBA", (2, 2), (1, 2, 3, 255)), 60), (Image.new("RGBA", (2, 2), (9, 9, 9, 255)), 50), (Image.new("RGBA", (2, 2), (1, 2, 3, 255)), 10)]
    mg = gif_to_frames.merge(fr); assert [d for _, d in mg] == [100, 50, 10]
    assert gif_to_frames.main([str(tmp_path / "a.gif"), "-o", str(tmp_path / "g"), "--merge-same", "--prefix", "x"]) == 0 and os.path.exists(tmp_path / "g" / "x_0002.png")


# ---------- tileset-from-image
def tmap(tsets, layers): return {"type": "map", "width": 4, "height": 1, "tilewidth": 8, "tileheight": 8, "tilesets": tsets, "layers": layers}


def test_tileset_audit(tmp_path):
    im = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    for i, c in {0: (255, 0, 0, 255), 1: (0, 255, 0, 255), 3: (255, 0, 0, 255), 4: (0, 0, 255, 255), 5: (255, 255, 0, 255), 6: (255, 255, 1, 255), 7: (0, 255, 255, 255)}.items():
        im.paste(Image.new("RGBA", (8, 8), c), ((i % 4) * 8, (i // 4) * 8))
    a = np.array(im); a[0, 0] = (0, 0, 0, 0); a[0, 24] = (9, 9, 9, 0)          # tiles 0 and 3 both have a transparent corner pixel, with different hidden colours: still duplicates
    Image.fromarray(a).save(tmp_path / "ts.png")
    ts = [{"firstgid": 1, "name": "ts", "image": "art/ts.png", "tilecount": 8, "columns": 4}]
    m1 = tmap(ts, [{"type": "tilelayer", "name": "g", "data": [1, 2, 0x80000000 | 5, 0]},
                   {"type": "group", "name": "grp", "layers": [{"type": "tilelayer", "name": "i", "data": [5, 0, 0, 0xE0000000 | 1]}]}, {"type": "objectgroup", "name": "o", "objects": []}])
    m2 = {"type": "map", "infinite": True, "tilesets": [{"firstgid": 10, "image": "ts.png", "tilecount": 8}], "layers": [{"type": "tilelayer", "name": "c", "chunks": [{"x": 0, "y": 0, "width": 2, "height": 1, "data": [10 + 7, 10 + 1]}]}]}
    rep, img = tileset_from_image.audit(str(tmp_path / "ts.png"), (8, 8), [("m1.json", m1), ("m2.json", m2)])
    assert rep["tiles"] == 8 and rep["empty"] == [2] and rep["duplicates"] == {"3": 0}
    assert rep["uses"] == [2, 2, 0, 0, 2, 0, 0, 1] and rep["unused"] == [3, 5, 6] and rep["per_map"] == {"m1.json": 5, "m2.json": 2}
    out = tileset_from_image.annotate(img, rep); assert out.size == img.size
    o = np.array(out); assert o[12, 12][1] < 250 and tuple(o[12, 28]) == (0, 255, 255, 255)        # unused tile 5 (yellow) is tinted red, used tile 7 is untouched
    # no match among several tilesets -> warning, nothing counted; single unmatched tileset -> assumed; --firstgid forces
    two = tmap([{"firstgid": 1, "image": "x.png"}, {"firstgid": 9, "image": "y.png"}], [{"type": "tilelayer", "name": "g", "data": [1, 1, 1, 1]}])
    r2, _ = tileset_from_image.audit(str(tmp_path / "ts.png"), (8, 8), [("two.json", two)]); assert r2["warnings"] and sum(r2["uses"]) == 0 and r2["unused"] == [] and r2["matched_maps"] == 0
    one = tmap([{"firstgid": 1, "image": "x.png"}], [{"type": "tilelayer", "name": "g", "data": [1, 1, 1, 1]}])
    r3, _ = tileset_from_image.audit(str(tmp_path / "ts.png"), (8, 8), [("one.json", one)]); assert r3["warnings"] and r3["uses"][0] == 4
    r4, _ = tileset_from_image.audit(str(tmp_path / "ts.png"), (8, 8), [("two.json", two)], forced_firstgid=1); assert r4["uses"][0] == 4 and not r4["warnings"]
    json.dump(m1, open(tmp_path / "m1.json", "w")); json.dump(m2, open(tmp_path / "m2.json", "w"))
    argv = [str(tmp_path / "ts.png"), str(tmp_path / "m1.json"), str(tmp_path / "m2.json"), "--tile", "8", "--json", str(tmp_path / "r.json"), "--png", str(tmp_path / "r.png")]
    assert tileset_from_image.main(argv) == 0 and tileset_from_image.main(argv + ["--fail-on-unused"]) == 1 and tileset_from_image.main(argv + ["--fail-on-duplicates"]) == 1
    assert json.load(open(tmp_path / "r.json"))["unused"] == [3, 5, 6] and Image.open(tmp_path / "r.png").size == (32, 16)
    assert tileset_from_image.main([str(tmp_path / "ts.png"), "--tile", "8x8"]) == 0
    json.dump(two, open(tmp_path / "two.json", "w")); assert tileset_from_image.main([str(tmp_path / "ts.png"), str(tmp_path / "two.json"), "--tile", "8"]) == 2            # nothing matched: say so instead of calling every tile unused
    enc = tmap(ts, [{"type": "tilelayer", "name": "g", "data": "AQID"}])
    with pytest.raises(SystemExit): tileset_from_image.audit(str(tmp_path / "ts.png"), (8, 8), [("e.json", enc)])


# ---------- map-diff
def lay(name, data, **kw): return dict({"type": "tilelayer", "name": name, "width": 3, "height": 2, "data": data}, **kw)


def test_map_diff(tmp_path):
    a = {"width": 3, "height": 2, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal", "properties": [{"name": "music", "value": "a"}],
         "tilesets": [{"name": "t", "firstgid": 1, "image": "t.png", "tilecount": 10}, {"name": "old", "firstgid": 11}],
         "layers": [lay("ground", [1, 1, 1, 1, 1, 1]), lay("walls", [0, 2, 0, 0, 0, 0]),
                    {"type": "objectgroup", "name": "things", "objects": [{"id": 1, "name": "spawn", "x": 10, "y": 10}, {"id": 2, "name": "key", "x": 5, "y": 5, "type": "item", "properties": [{"name": "colour", "value": "red"}]}, {"id": 3, "name": "gone", "x": 0, "y": 0}]},
                    {"type": "group", "name": "fx", "layers": [lay("mist", [0] * 6)]}]}
    b = json.loads(json.dumps(a)); b["width"] = 4; b["properties"][0]["value"] = "b"; b["tilesets"][0]["tilecount"] = 12; b["tilesets"] = b["tilesets"][:1] + [{"name": "new", "firstgid": 20}]
    b["layers"][0]["data"] = [1, 3, 1, 1, 3, 1]; b["layers"][1]["data"] = [0, 2, 0, 0, 0, 0x80000000 | 2]; b["layers"][1]["opacity"] = 0.5
    objs = b["layers"][2]["objects"]; objs[0]["x"] = 12; objs[1]["properties"][0]["value"] = "blue"; objs[1]["name"] = "KEY"; objs.pop(2); objs.append({"id": 9, "name": "boss", "x": 1, "y": 2, "type": "enemy"})
    b["layers"].insert(0, lay("sky", [0] * 6)); b["layers"][4]["layers"][0]["data"] = [4, 0, 0, 0, 0, 0]
    d = map_diff.diff(a, b)
    assert d["map"]["width"] == [3, 4] and d["map"]["properties"]["music"] == ["a", "b"] and d["has_changes"]
    assert d["tilesets"]["added"] == ["new"] and d["tilesets"]["removed"] == ["old"] and d["tilesets"]["changed"][0]["changes"] == {"tilecount": [10, 12]}
    assert d["layers"]["added"] == ["sky"] and d["layers"]["removed"] == [] and d["layers"]["order_changed"] is False
    g = d["layers"]["changed"]["ground"]["tiles"]; assert g["changed"] == 2 and g["bbox"] == [1, 0, 1, 1] and g["top_swaps"] == [[1, 3, 2]] and g["added"] == 0
    w = d["layers"]["changed"]["walls"]; assert w["tiles"]["added"] == 1 and w["tiles"]["changed"] == 1 and w["opacity"] == [None, 0.5]
    o = d["layers"]["changed"]["things"]["objects"]
    assert [x["id"] for x in o["added"]] == [9] and [x["id"] for x in o["removed"]] == [3] and o["moved"][0]["from"] == [10, 10] and o["moved"][0]["to"] == [12, 10]
    assert o["edited"][0]["changes"]["name"] == ["key", "KEY"] and o["edited"][0]["changes"]["properties"] == {"colour": ["red", "blue"]}
    assert d["layers"]["changed"]["fx/mist"]["tiles"]["added"] == 1                        # nested group layer matched by path
    c = json.loads(json.dumps(a)); c["layers"] = [c["layers"][1], c["layers"][0]] + c["layers"][2:]; assert map_diff.diff(a, c)["layers"]["order_changed"]
    assert not map_diff.diff(a, a)["has_changes"] and map_diff.lines(map_diff.diff(a, a)) == []
    inf_a = {"layers": [{"type": "tilelayer", "name": "i", "chunks": [{"x": -2, "y": 0, "width": 2, "height": 1, "data": [1, 0]}]}]}
    inf_b = {"layers": [{"type": "tilelayer", "name": "i", "chunks": [{"x": -2, "y": 0, "width": 2, "height": 1, "data": [1, 5]}]}]}
    t = map_diff.diff(inf_a, inf_b)["layers"]["changed"]["i"]["tiles"]; assert t["bbox"] == [-1, 0, -1, 0] and t["added"] == 1
    json.dump(a, open(tmp_path / "a.json", "w")); json.dump(b, open(tmp_path / "b.json", "w"))
    assert map_diff.main([str(tmp_path / "a.json"), str(tmp_path / "b.json"), "--md", str(tmp_path / "d.md"), "--json", str(tmp_path / "d.json")]) == 0
    assert map_diff.main([str(tmp_path / "a.json"), str(tmp_path / "b.json"), "--fail-on-diff"]) == 1 and map_diff.main([str(tmp_path / "a.json"), str(tmp_path / "a.json"), "--fail-on-diff"]) == 0
    assert "walls" in open(tmp_path / "d.md").read() and json.load(open(tmp_path / "d.json"))["has_changes"]


# ---------- mesh-pivot-fix
def cube_obj(path, lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    V = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    open(path, "w").write("o cube\n" + "".join(f"v {x} {y} {z}\n" for x, y, z in V) + "f 1 2 4 3\nf 5 7 8 6\nf 1 5 6 2\nf 3 4 8 7\nf 1 3 7 5\nf 2 6 8 4\n")


def test_pivot_glb(tmp_path):
    cube_obj(tmp_path / "c.obj", (10, 5, -3), (12, 7, -1))
    g, b = obj_to_glb.convert(str(tmp_path / "c.obj")); obj_to_glb.write_glb(str(tmp_path / "c.glb"), g, b)
    raw_before = open(tmp_path / "c.glb", "rb").read()
    assert mesh_pivot_fix.main([str(tmp_path / "c.glb"), "-o", str(tmp_path / "o.glb"), "--mode", "bottom"]) == 0
    js, chunks, ver = mesh_pivot_fix.read_glb(str(tmp_path / "o.glb")); lo, hi = mesh_pivot_fix.world_bounds(js)
    assert np.allclose(lo, [-1, 0, -1]) and np.allclose(hi, [1, 2, 1])
    js0, chunks0, _ = mesh_pivot_fix.read_glb(str(tmp_path / "c.glb")); assert [c for t, c in chunks if t == b"BIN\x00"] == [c for t, c in chunks0 if t == b"BIN\x00"]    # vertex data untouched
    loaded, bin_chunk = gltf_inspect.load(str(tmp_path / "o.glb")); assert loaded["asset"] and bin_chunk
    assert open(tmp_path / "c.glb", "rb").read() == raw_before                                                      # input never modified
    for mode, want in (("center", ([-1, -1, -1], [1, 1, 1])), ("min", ([0, 0, 0], [2, 2, 2]))):
        r = mesh_pivot_fix.fix_gltf(json.loads(json.dumps(js0)), mode); assert np.allclose(r["after"]["min"], want[0]) and np.allclose(r["after"]["max"], want[1]), mode
    r = mesh_pivot_fix.fix_gltf(json.loads(json.dumps(js0)), "point", [11, 5, -2]); assert np.allclose(r["after"]["min"], [-1, 0, -1])
    assert mesh_pivot_fix.main([str(tmp_path / "c.glb"), "--report"]) == 0
    with pytest.raises(SystemExit): mesh_pivot_fix.main([str(tmp_path / "c.glb"), "--mode", "point"])


def test_pivot_transforms():
    # hand-built scene: a unit-box mesh (POSITION min/max only), child offset, root rotated 90 degrees about Y and scaled 2, plus a matrix root
    s = math.sqrt(0.5)
    js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0, 3]}],
          "nodes": [{"translation": [4, 1, 0], "rotation": [0, s, 0, s], "scale": [2, 2, 2], "children": [1]}, {"mesh": 0, "translation": [1, 0, 0]}, {}, {"matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 20, 0, 0, 1], "mesh": 0}],
          "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}], "accessors": [{"min": [-1, -1, -1], "max": [1, 1, 1]}]}
    lo, hi = mesh_pivot_fix.world_bounds(js)
    # child box x in [0,2] after offset; scale 2 -> [0,4]; rotate +90deg about Y maps x -> -z: z in [-4,0]; box y [-2,2]+1 = [-1,3]; root x 4 => x in [2,6]; matrix root box x in [19,21]
    assert np.allclose(lo, [2, -1, -4]) and np.allclose(hi, [21, 3, 1])
    r = mesh_pivot_fix.fix_gltf(js, "bottom"); assert np.allclose(r["after"]["min"][1], 0) and np.allclose((np.array(r["after"]["min"]) + np.array(r["after"]["max"]))[[0, 2]], 0)
    assert js["nodes"][3]["matrix"][12] == pytest.approx(20 - 11.5) and js["nodes"][0]["translation"][1] == pytest.approx(1 - -1)
    js["skins"] = [{}]; js["animations"] = [{"name": "walk", "channels": [{"target": {"node": 0, "path": "translation"}}]}]
    w = mesh_pivot_fix.fix_gltf(js, "center")["warnings"]; assert len(w) == 2
    with pytest.raises(SystemExit): mesh_pivot_fix.world_bounds({"nodes": [{}], "scenes": [{"nodes": [0]}]})


def test_pivot_obj(tmp_path):
    cube_obj(tmp_path / "c.obj", (10, 5, -3), (12, 7, -1)); open(tmp_path / "c.obj", "a").write("# keep me\n")
    assert mesh_pivot_fix.main([str(tmp_path / "c.obj"), "-o", str(tmp_path / "o.obj")]) == 0
    V = np.array([[float(x) for x in l.split()[1:4]] for l in open(tmp_path / "o.obj") if l.startswith("v ")]); assert np.allclose(V.min(0), [-1, 0, -1]) and np.allclose(V.max(0), [1, 2, 1])
    txt = open(tmp_path / "o.obj").read(); assert "f 1 2 4 3" in txt and "# keep me" in txt
    mesh_pivot_fix.main([str(tmp_path / "c.obj"), "-o", str(tmp_path / "z.obj"), "--up", "z"]); V = np.array([[float(x) for x in l.split()[1:4]] for l in open(tmp_path / "z.obj") if l.startswith("v ")]); assert V[:, 2].min() == 0 and np.allclose(V[:, :2].min(0), [-1, -1])
    with pytest.raises(SystemExit): mesh_pivot_fix.main([str(tmp_path / "x.fbx")])


# ---------- voice-slate
YARN = """title: Start
---
Anna: Hello there, traveler. Welcome to the village of Oakfield. #line:a1 #angry
Bob: Hi.
-> Ask about the well
Anna: The well is cursed.
===
title: Well
---
Bob: I will take a look at it myself, thank you very much for the warning.
Narrator text without a speaker.
Anna: Be careful.
===
"""


def test_voice_slate(tmp_path):
    (tmp_path / "s.yarn").write_text(YARN)
    rows = voice_slate.load_rows([str(tmp_path / "s.yarn")]); p = voice_slate.plan(rows, takes=2, overhead=5, session_min=120)
    assert sorted(p) == ["Anna", "Bob"] and p["Anna"]["lines"] == 3 and p["Bob"]["lines"] == 2 and "Narrator" not in p
    a = p["Anna"]["items"]; assert a[0]["take_id"] == "anna-001" and a[0]["line_id"] == "a1" and a[0]["direction"] == "angry" and a[0]["target"] == "anna_a1.wav" and a[0]["node"] == "Start"
    assert a[0]["budget_seconds"] == pytest.approx(a[0]["est_seconds"] * 2 + 5) and len(p["Anna"]["sessions"]) == 1
    assert "Narrator" in voice_slate.plan(rows, narrator="Narrator")
    # tiny sessions split; prefer a node boundary when the first part is at least half full
    small = voice_slate.plan(rows, takes=1, overhead=0, session_min=0.1)["Bob"]; assert len(small["sessions"]) == 2 and [i["session"] for i in small["items"]] == [1, 2]
    no = voice_slate.plan([r for r in rows if r["kind"] != "choice"], narrator=None)["Anna"]["lines"]; assert no == 3
    assert voice_slate.main([str(tmp_path / "s.yarn"), "-o", str(tmp_path / "out"), "--skip-choices", "--speaker", "anna"]) == 0
    assert (tmp_path / "out" / "anna.csv").exists() and not (tmp_path / "out" / "bob.csv").exists() and "Anna, session 1 of 1" in (tmp_path / "out" / "slate.md").read_text()
    import csv
    r = list(csv.DictReader(open(tmp_path / "out" / "anna.csv"))); assert len(r) == 3 and r[0]["take_no"] == "" and r[0]["target"] == "anna_a1.wav"
    import dialogue_extract
    dialogue_extract.main([str(tmp_path / "s.yarn"), "-o", str(tmp_path / "lines.csv")])
    assert voice_slate.main([str(tmp_path / "lines.csv"), "-o", str(tmp_path / "out2"), "--pattern", "vo/{speaker}/{n}.wav"]) == 0 and "vo/bob/1.wav" in (tmp_path / "out2" / "slate.md").read_text()
    with pytest.raises(SystemExit): voice_slate.load_rows(["x.txt"])
    (tmp_path / "e.yarn").write_text("title: A\n---\nplain narration only\n===\n")
    with pytest.raises(SystemExit): voice_slate.main([str(tmp_path / "e.yarn"), "-o", str(tmp_path / "o3")])


# ---------- wav-batch-meta
def wavfile(path, x, sr=48000, bits=16):
    audio_tidy.write_wav(str(path), x, sr, bits)


def sine(f, amp, secs, sr=48000, ch=2):
    t = np.arange(int(sr * secs)) / sr; x = amp * np.sin(2 * np.pi * f * t); return np.stack([x] * ch, 1) if ch > 1 else x[:, None]


def test_k_filter_constants():
    (b1, a1), (b2, a2) = wav_batch_meta.k_filters(48000)             # the published 48 kHz BS.1770 coefficients
    assert np.allclose(b1, [1.53512485958697, -2.69169618940638, 1.19839281085285], atol=1e-8) and np.allclose(a1, [1, -1.69065929318241, 0.73248077421585], atol=1e-8)
    assert np.allclose(a2, [1, -1.99004745483398, 0.99007225036621], atol=1e-8) and b2 == [1.0, -2.0, 1.0]


def test_lufs_reference_signals():
    amp = 10 ** (-23 / 20)
    i, mom, short = wav_batch_meta.lufs(sine(1000, amp, 5), 48000); assert i == pytest.approx(-23.0, abs=0.1) and not short and mom == pytest.approx(-23.0, abs=0.1)       # EBU Tech 3341: -23 dBFS stereo 1 kHz = -23 LUFS
    i, _, _ = wav_batch_meta.lufs(sine(1000, amp, 5, ch=1), 48000); assert i == pytest.approx(-26.0, abs=0.1)                  # one channel is 3 dB quieter
    i, _, _ = wav_batch_meta.lufs(sine(1000, 0.1, 4, sr=44100), 44100); assert i == pytest.approx(-20.0, abs=0.1)            # works at other rates
    # absolute gate: silence around a tone does not drag the result down
    x = np.concatenate([np.zeros((48000 * 2, 2)), sine(1000, amp, 3), np.zeros((48000 * 2, 2))]); assert wav_batch_meta.lufs(x, 48000)[0] == pytest.approx(-23.0, abs=0.5)           # edge blocks hold part of the tone (kept by BS.1770); without the absolute gate this would be about -26.7
    # relative gate: a very quiet section (more than 10 LU under) is ignored
    x = np.concatenate([sine(1000, 0.1, 3), sine(1000, 0.001, 6)]); assert wav_batch_meta.lufs(x, 48000)[0] == pytest.approx(-20.0, abs=0.3)
    i, mom, short = wav_batch_meta.lufs(sine(1000, 0.1, 0.2), 48000); assert short and i == pytest.approx(-20.0, abs=0.5)
    assert wav_batch_meta.lufs(np.zeros((48000, 2)), 48000)[0] is None
    assert wav_batch_meta.lufs(sine(60, 0.5, 3), 48000)[0] < wav_batch_meta.lufs(sine(1000, 0.5, 3), 48000)[0] - 1          # the high-pass stage cuts deep bass


def test_true_peak_and_measure(tmp_path):
    t = np.arange(4800)                                                      # fs/4 sine at 45 degrees: every sample sits at 0.636 but the waveform peaks at 0.9
    x = (0.9 * np.sin(2 * np.pi * t / 4 + np.pi / 4))[:, None] * np.ones((1, 2))
    assert np.abs(x).max() == pytest.approx(0.9 * math.sqrt(0.5), abs=1e-6)
    assert wav_batch_meta.true_peak_db(x) == pytest.approx(20 * math.log10(0.9), abs=0.05) and wav_batch_meta.true_peak_db(x) > audio_tidy.db(np.abs(x).max()) + 2.5
    wavfile(tmp_path / "t.wav", np.clip(x, -1, 1)); m = wav_batch_meta.measure(str(tmp_path / "t.wav"))
    assert m["channels"] == 2 and m["bits"] == 16 and m["duration_s"] == 0.1 and m["clipped"] == 0 and m["dc_offset"] < 1e-3 and m["short"] is True
    clip = sine(200, 1.5, 1); wavfile(tmp_path / "c.wav", np.clip(clip, -1, 1)); assert wav_batch_meta.measure(str(tmp_path / "c.wav"))["clipped"] > 1000
    pad = np.concatenate([np.zeros((4800, 1)), sine(440, 0.3, 1, ch=1), np.zeros((9600, 1))]); wavfile(tmp_path / "p.wav", pad, bits=24)
    m = wav_batch_meta.measure(str(tmp_path / "p.wav")); assert m["bits"] == 24 and m["lead_silence_ms"] == pytest.approx(100, abs=2) and m["trail_silence_ms"] == pytest.approx(200, abs=2)
    dc = sine(200, 0.1, 1, ch=1) + 0.05; wavfile(tmp_path / "d.wav", dc); m = wav_batch_meta.measure(str(tmp_path / "d.wav")); ok = wav_batch_meta.judge(m, None, 1, -1); assert "DC" in m["flags"] and ok


def test_wav_batch_cli(tmp_path):
    (tmp_path / "music").mkdir(); (tmp_path / "sfx").mkdir()
    wavfile(tmp_path / "music" / "m.wav", sine(1000, 10 ** (-16 / 20), 4)); wavfile(tmp_path / "sfx" / "ok.wav", sine(1000, 10 ** (-18 / 20), 3)); wavfile(tmp_path / "sfx" / "loud.wav", sine(1000, 0.95, 3))
    base = [str(tmp_path), "--csv", str(tmp_path / "r.csv"), "--json", str(tmp_path / "r.json"), "--quiet"]
    assert wav_batch_meta.main(base) == 1                                                                                       # no target: only technical flags can fail (loud.wav peaks above -1 dBTP)
    first = {os.path.basename(r["file"]): r for r in json.load(open(tmp_path / "r.json"))}; assert first["m.wav"]["ok"] and first["ok.wav"]["ok"] and first["loud.wav"]["flags"] == ["TP_OVER"] and "suggested_gain_db" not in first["m.wav"]
    assert wav_batch_meta.main(base + ["--rule", "music/*=-16", "--rule", "sfx/*=-18", "--max-true-peak", "-1"]) == 1          # loud.wav is off target and over the true-peak ceiling
    rows = {os.path.basename(r["file"]): r for r in json.load(open(tmp_path / "r.json"))}
    assert rows["m.wav"]["ok"] and rows["ok.wav"]["ok"] and not rows["loud.wav"]["ok"] and {"OFF_TARGET", "TP_OVER"} <= set(rows["loud.wav"]["flags"])
    assert rows["loud.wav"]["suggested_gain_db"] == pytest.approx(-18 - rows["loud.wav"]["lufs"], abs=0.01) and rows["loud.wav"]["lufs"] > -1
    m = {"lufs": -30.0, "true_peak_db": -3.0, "peak_db": -3.0, "clipped": 0, "dc_offset": 0, "short": False, "silent": False}; wav_batch_meta.judge(m, -16, 1, -1); assert m["suggested_gain_db"] == 2.0 and "OFF_TARGET" in m["flags"]   # +14 LU wanted, the -1 dBTP ceiling allows +2
    assert rows["ok.wav"]["suggested_gain_db"] == pytest.approx(0.0, abs=0.15) and rows["m.wav"]["lufs"] == pytest.approx(-16.0, abs=0.15)
    assert "lufs" in open(tmp_path / "r.csv").readline()
    assert wav_batch_meta.main([str(tmp_path / "music"), "--target", "-16", "--quiet"]) == 0 and wav_batch_meta.main([str(tmp_path / "music" / "m.wav"), "--target", "-23", "--tolerance", "2", "--quiet"]) == 1
    (tmp_path / "bad.wav").write_bytes(b"not a wav"); assert wav_batch_meta.main([str(tmp_path / "bad.wav"), "--quiet"]) == 1
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit): wav_batch_meta.main([str(tmp_path / "empty")])


# ---------- input-map-lint
GODOT = '''; Engine configuration file.
config_version=5

[application]
config/name="Demo"

[input]

jump={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":32,"key_label":0,"unicode":32,"echo":false,"script":null)
, Object(InputEventJoypadButton,"resource_local_to_scene":false,"resource_name":"","device":-1,"button_index":0,"pressure":0.0,"pressed":false,"script":null)
]
}
confirm={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"physical_keycode":32,"script":null)
]
}
sprint={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"alt_pressed":false,"shift_pressed":true,"ctrl_pressed":false,"meta_pressed":false,"physical_keycode":87,"script":null)
]
}
move_up={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"physical_keycode":87,"script":null)
, Object(InputEventJoypadMotion,"resource_local_to_scene":false,"device":-1,"axis":1,"axis_value":-1.0,"script":null)
, Object(InputEventMouseButton,"resource_local_to_scene":false,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"button_mask":0,"position":Vector2(0, 0),"global_position":Vector2(0, 0),"factor":1.0,"button_index":4,"canceled":false,"pressed":false,"double_click":false,"script":null)
]
}
empty_action={
"deadzone": 0.5,
"events": []
}

[rendering]
renderer/rendering_method="mobile"
'''


def test_input_map_godot_parse(tmp_path):
    (tmp_path / "project.godot").write_text(GODOT); c = input_map_lint.parse_godot(str(tmp_path / "project.godot"))["all"]
    assert set(c) == {"jump", "confirm", "sprint", "move_up", "empty_action"} and c["jump"] == [("key", "space", ()), ("pad", "button0", ())] and c["sprint"] == [("key", "w", ("shift",))]
    assert c["move_up"] == [("key", "w", ()), ("pad", "axis1-", ()), ("mouse", "wheelup", ())] and c["empty_action"] == []


def test_input_map_lint(tmp_path):
    (tmp_path / "project.godot").write_text(GODOT)
    F = input_map_lint.lint(input_map_lint.parse_godot(str(tmp_path / "project.godot")), parity=True); codes = {(f["severity"], f["code"]) for f in F}
    assert ("error", "unbound") in codes and ("error", "conflict") in codes and ("warning", "shadowed") in codes and ("warning", "no-gamepad") in codes
    conflict = [f for f in F if f["code"] == "conflict"]; assert len(conflict) == 1 and "'jump'" in conflict[0]["message"] and "'confirm'" in conflict[0]["message"]
    assert [f["message"] for f in F if f["code"] == "no-gamepad"] and not any("'jump'" in f["message"] for f in F if f["code"] == "no-gamepad")
    allowed = input_map_lint.lint(input_map_lint.parse_godot(str(tmp_path / "project.godot")), allow=[["confirm", "jump"]]); assert not [f for f in allowed if f["code"] == "conflict"]
    # JSON forms, naming, duplicates, contexts, ui_ ignoring
    j = {"actions": {"Jump": ["Key:Space", "key:space", "Pad:A"], "jump": ["Pad:B"], "fire": ["Mouse:Left", {"device": "key", "code": "F", "mods": ["Ctrl"]}], "ui_accept": ["Key:Enter"], "ui_select": ["Key:Enter"], "bad name": ["Key:X"]}}
    json.dump(j, open(tmp_path / "m.json", "w")); F = input_map_lint.lint(input_map_lint.load_json(str(tmp_path / "m.json"))); codes = {f["code"] for f in F}
    assert {"name-case", "duplicate-binding", "name-style"} <= codes and "conflict" not in codes
    assert [f for f in input_map_lint.lint(input_map_lint.load_json(str(tmp_path / "m.json")), include_ui=True) if f["code"] == "conflict"]
    ctx = {"contexts": {"play": {"jump": ["Key:Space"]}, "menu": {"select": ["Key:Space"]}}}; json.dump(ctx, open(tmp_path / "c.json", "w"))
    assert not [f for f in input_map_lint.lint(input_map_lint.load_json(str(tmp_path / "c.json"))) if f["severity"] == "error"]
    one = {"play": {k: [input_map_lint.norm(v)] for k, v in (("jump", "Key:Space"), ("select", "Key:Space"))}}; assert [f for f in input_map_lint.lint(one) if f["code"] == "conflict"]
    assert input_map_lint.norm("Keyboard:Shift+W") == ("key", "w", ("shift",)) and input_map_lint.norm("Joy:A") == ("pad", "a", ()) and input_map_lint.norm("Space") == ("key", "space", ())


def test_input_map_scan_and_cli(tmp_path):
    code = tmp_path / "src"; code.mkdir(); (code / "player.gd").write_text('func _p():\n\tif Input.is_action_just_pressed("jump"): pass\n\tvar v = Input.get_vector("left", "right", "up", "down")\n\tInput.get_action_strength(&"sprint")\n')
    (code / "Hud.cs").write_text('if (Input.IsActionPressed("fire")) {}\nvar name = "unused_but_mentioned";\n'); (code / "node_modules").mkdir(); (code / "node_modules" / "x.js").write_text('is_action_pressed("hidden")')
    used, alls = input_map_lint.scan_code(str(code)); assert set(used) == {"jump", "left", "right", "up", "down", "sprint", "fire"} and "unused_but_mentioned" in alls
    m = {"jump": ["Key:Space"], "sprint": ["Key:Shift"], "left": ["Key:A"], "right": ["Key:D"], "up": ["Key:W"], "orphan": ["Key:Q"], "unused_but_mentioned": ["Key:Z"]}
    F = input_map_lint.lint({"all": {k: [input_map_lint.norm(b) for b in v] for k, v in m.items()}}, used=used, alls=alls); by = {(f["code"], f["message"].split("'")[1]) for f in F}
    assert ("undefined", "down") in by and ("undefined", "fire") in by and ("unused", "orphan") in by and ("unused", "unused_but_mentioned") not in by
    json.dump(m, open(tmp_path / "m.json", "w")); assert input_map_lint.main([str(tmp_path / "m.json"), "--scan", str(code), "--json", str(tmp_path / "o.json")]) == 1 and len(json.load(open(tmp_path / "o.json"))) == len(F)
    ok = {"jump": ["Key:Space"], "orphan": ["Key:Q"]}; json.dump(ok, open(tmp_path / "ok.json", "w"))
    assert input_map_lint.main([str(tmp_path / "ok.json")]) == 0 and input_map_lint.main([str(tmp_path / "ok.json"), "--parity", "--strict"]) == 1
    (tmp_path / "bad.godot").write_text("[application]\nx=1\n")
    with pytest.raises(SystemExit): input_map_lint.main([str(tmp_path / "bad.godot")])


def test_audio_tidy_write_wav_bit_depths(tmp_path):
    x = np.array([[0.5], [-0.25], [0.0], [0.999]])
    for bits in (16, 24, 32):
        audio_tidy.write_wav(str(tmp_path / f"{bits}.wav"), x, 8000, bits); y, sr = audio_tidy.read_wav(str(tmp_path / f"{bits}.wav"))
        assert sr == 8000 and y.shape == (4, 1) and np.abs(y - x).max() < max(2.0 / 2 ** (bits - 1), 2e-7), bits    # read_wav returns float32
    assert os.path.getsize(tmp_path / "24.wav") == 44 + 4 * 3
    with pytest.raises(ValueError): audio_tidy.write_wav(str(tmp_path / "x.wav"), x, 8000, 12)
