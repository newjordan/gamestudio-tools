import base64, gzip, json, os, struct, math, zlib
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from gst_errors import GstInputError
from PIL import Image, ImageFont
import tilemap_stats, sprite_outline_gen, frame_timing_check, cue_sheet, level_budget, gltf_strip, text_wrap_bake, spritesheet_gif
import audio_tidy, wav_loop_meta, obj_to_glb, gltf_inspect, loc_fit, map_diff


# ---------- tilemap-stats
def tmap(layers, **kw):
    m = {"type": "map", "width": 4, "height": 2, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal",
         "tilesets": [{"name": "ground", "firstgid": 1, "tilecount": 10}, {"name": "props", "firstgid": 20, "tilecount": 5}],
         "layers": layers}
    m.update(kw); return m


def test_tilemap_stats(tmp_path):
    m = tmap([
        {"type": "tilelayer", "name": "base", "width": 4, "height": 2, "data": [1, 1, 2, 0, 1, 0x80000000 | 2, 20, 0]},
        {"type": "tilelayer", "name": "empty", "width": 4, "height": 2, "visible": False, "data": [0] * 8},
        {"type": "group", "name": "fg", "layers": [
            {"type": "objectgroup", "name": "mobs", "objects": [{"id": 1, "name": "bat", "type": "enemy", "x": 0, "y": 0},
                                                               {"id": 2, "name": "slime", "type": "enemy", "x": 1, "y": 1},
                                                               {"id": 3, "name": "coin", "type": "pickup", "x": 2, "y": 2}]}]},
        {"type": "objectgroup", "name": "idle", "objects": []},
    ])
    s = tilemap_stats.stats_one("level.json", m)
    assert s["width"] == 4 and s["objects"] == 3
    base = s["tile_layers"][0]; assert base["name"] == "base" and base["empty"] == 2 and base["unique_tiles"] == 3 and base["flipped"] == 1
    assert base["most_used"][0] == [1, 3] and base["empty_ratio"] == 0.25
    assert "empty" in s["empty_layers"] and "idle" in s["empty_layers"] and "empty" in s["hidden_layers"]
    assert s["object_layers"][0]["name"] == "fg/mobs" and s["object_layers"][0]["by_type"] == {"enemy": 2, "pickup": 1}
    assert s["unused_tilesets"] == [] and s["tilesets"][0]["unique_used"] == 2 and s["tilesets"][1]["uses"] == 1
    # unused tileset, infinite chunks, malformed encoded data still refused, valid base64+zlib is decoded
    m2 = tmap([{"type": "tilelayer", "name": "g", "chunks": [{"x": 0, "y": 0, "width": 2, "height": 1, "data": [1, 0]}]}], infinite=True)
    s2 = tilemap_stats.stats_one("inf.json", m2); assert s2["infinite"] and s2["tile_layers"][0]["empty"] == 1 and "props" in s2["unused_tilesets"]
    with pytest.raises(GstInputError): tilemap_stats.stats_one("e.json", tmap([{"type": "tilelayer", "name": "g", "data": "AQID"}]))  # 3 bytes, not a multiple of 4
    raw = struct.pack("<8I", 1, 1, 2, 0, 1, 0x80000000 | 2, 20, 0)
    m_enc = tmap([{"type": "tilelayer", "name": "g", "width": 4, "height": 2, "encoding": "base64", "compression": "zlib",
                   "data": base64.b64encode(zlib.compress(raw)).decode()}])
    se = tilemap_stats.stats_one("enc.json", m_enc)
    assert se["tile_layers"][0]["empty"] == 2 and se["tile_layers"][0]["unique_tiles"] == 3 and se["tile_layers"][0]["flipped"] == 1
    raw_gz = base64.b64encode(gzip.compress(struct.pack("<2I", 1, 0))).decode()
    sg = tilemap_stats.stats_one("gz.json", tmap([{"type": "tilelayer", "name": "g", "width": 2, "height": 1, "encoding": "base64", "compression": "gzip", "data": raw_gz}]))
    assert sg["tile_layers"][0]["empty"] == 1 and sg["tile_layers"][0]["unique_tiles"] == 1
    json.dump(m, open(tmp_path / "level.json", "w")); json.dump(m2, open(tmp_path / "inf.json", "w"))
    argv = [str(tmp_path / "level.json"), str(tmp_path / "inf.json"), "--json", str(tmp_path / "s.json"), "--csv", str(tmp_path / "s.csv")]
    assert tilemap_stats.main(argv) == 0 and tilemap_stats.main(argv + ["--fail-on-empty-layer"]) == 1
    assert tilemap_stats.main([str(tmp_path / "inf.json"), "--fail-on-unused-tileset"]) == 1
    assert tilemap_stats.main([str(tmp_path / "level.json"), "--fail-on-hidden"]) == 1
    rows = json.load(open(tmp_path / "s.json")); assert isinstance(rows, list) and rows[0]["file"] == "level.json" and "empty_layers" in open(tmp_path / "s.csv").read()


# ---------- sprite-outline-gen
def solid_square(s=7, box=(2, 2, 5, 5), color=(255, 0, 0, 255)):
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0)); im.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), color), box[:2]); return im


def test_sprite_outline():
    im = solid_square(); a = np.array(im)
    outer, pad = sprite_outline_gen.apply([im], 1, "outer", eight=False, color=(0, 0, 0, 255)); o = np.array(outer[0])
    assert pad == 1 and outer[0].size == (9, 9)
    # the original square is still red, shifted by 1
    assert tuple(o[3, 3]) == (255, 0, 0, 255) and tuple(o[1, 1]) == (0, 0, 0, 0)
    # 4-connected outer ring: orthogonal neighbours of the square (now at 3..5 inclusive) are black
    assert tuple(o[2, 3]) == (0, 0, 0, 255) and tuple(o[3, 2]) == (0, 0, 0, 255)
    assert tuple(o[2, 2]) == (0, 0, 0, 0)                                                                  # diagonal is not painted in 4-connect
    eight, _ = sprite_outline_gen.apply([im], 1, "outer", eight=True, color=(0, 0, 255, 255)); e = np.array(eight[0])
    assert tuple(e[2, 2]) == (0, 0, 255, 255)                                                              # diagonal is painted in 8-connect
    inner, p0 = sprite_outline_gen.apply([im], 1, "inner", eight=False, color=(0, 0, 0, 255)); inn = np.array(inner[0])
    assert p0 == 0 and inner[0].size == (7, 7)
    assert tuple(inn[2, 2]) == (0, 0, 0, 255) and tuple(inn[3, 3]) == (255, 0, 0, 255) and inn[1, 1, 3] == 0   # inner ring sits on the old edge; centre stays; outside stays empty
    both, _ = sprite_outline_gen.apply([im], 1, "both", eight=False, color=(0, 255, 0, 255)); b = np.array(both[0])
    assert both[0].size == (9, 9) and tuple(b[2, 3]) == (0, 255, 0, 255) and tuple(b[3, 3]) == (0, 255, 0, 255)
    # two frames of different sizes share one padding and so one "added" border; keep-size crops back
    a, b = solid_square(7), solid_square(5, (1, 1, 4, 4))
    outs, pad = sprite_outline_gen.apply([a, b], 2, "outer"); assert pad == 2 and outs[0].size == (11, 11) and outs[1].size == (9, 9)
    kept, _ = sprite_outline_gen.apply([im], 1, "outer", keep_size=True); assert kept[0].size == (7, 7)


def test_sprite_outline_cli(tmp_path):
    solid_square().save(tmp_path / "a.png"); solid_square().save(tmp_path / "b.png")
    assert sprite_outline_gen.main([str(tmp_path / "a.png"), str(tmp_path / "b.png"), "-o", str(tmp_path / "out"), "--width", "1", "--connect", "4"]) == 0
    assert Image.open(tmp_path / "out" / "a.png").size == (9, 9)
    sheet = Image.new("RGBA", (14, 7), (0, 0, 0, 0)); sheet.paste(solid_square(), (0, 0)); sheet.paste(solid_square(), (7, 0)); sheet.save(tmp_path / "s.png")
    assert sprite_outline_gen.main([str(tmp_path / "s.png"), "-o", str(tmp_path / "s2.png"), "--grid", "7x7", "--mode", "inner"]) == 0
    assert Image.open(tmp_path / "s2.png").size == (14, 7)                                                                # inner outline: sheet size unchanged
    assert sprite_outline_gen.main([str(tmp_path / "s.png"), "-o", str(tmp_path / "s3.png"), "--grid", "7x7", "--width", "1"]) == 0
    assert Image.open(tmp_path / "s3.png").size == (18, 9)
    assert sprite_outline_gen.parse_color("#00ff00aa") == (0, 255, 0, 170)
    with pytest.raises(SystemExit): sprite_outline_gen.main([str(tmp_path / "a.png"), "-o", str(tmp_path / "z.png"), "--width", "0"])
    with pytest.raises(SystemExit): sprite_outline_gen.parse_color("red")


# ---------- frame-timing-check
CLIPS = {"clips": {
    "idle": {"frames": ["a", "b"], "durations_ms": [100, 100], "fps": 10, "loop": True, "duration": 0.2},
    "run": {"frames": ["c", "d", "e"], "durations_ms": [80, 100, 120], "fps": 10, "loop": True, "duration": 0.3},
    "hold": {"frames": ["x"], "durations_ms": [1000], "fps": 1, "loop": True, "duration": 1.0},
}}


def test_frame_timing_load_and_check():
    clips = frame_timing_check.load_clips(CLIPS)
    F = frame_timing_check.check(clips, fps=10, tolerance_ms=1.0)
    codes = {(f["clip"], f["code"], f["severity"]) for f in F}
    assert ("run", "off-grid", "error") in codes and ("run", "variable", "warning") in codes
    assert ("hold", "single-loop", "warning") in codes
    assert not any(f["clip"] == "idle" and f["code"] == "off-grid" for f in F)
    ok = frame_timing_check.check(clips, fps=10, tolerance_ms=20, allow_variable=True)
    assert not any(f["code"] in ("off-grid", "variable") for f in ok)
    assert any(f["code"] == "too-short" for f in frame_timing_check.check(clips, min_ms=90) if f["clip"] == "run")
    assert any(f["code"] == "short-clip" for f in frame_timing_check.check(clips, min_clip=0.5) if f["clip"] == "idle")
    # durations implied from fps only
    bare = frame_timing_check.load_clips({"clips": {"w": {"frames": ["a", "b", "c"], "fps": 12, "loop": False}}})
    assert bare["w"]["durations_ms"] == [83, 83, 83]
    # Phaser
    ph = frame_timing_check.load_clips({"anims": [{"key": "walk", "frameRate": 8, "repeat": -1, "frames": [{"key": "atlas", "frame": "w_0"}, {"key": "atlas", "frame": "w_1"}]}]})
    assert ph["walk"]["loop"] is True and ph["walk"]["durations_ms"] == [125, 125] and ph["walk"]["frames"] == ["w_0", "w_1"]
    # gif-to-frames list
    fr = frame_timing_check.load_clips({"frames": [{"file": "f0.png", "duration_ms": 40}, {"file": "f1.png", "duration_ms": 60}], "total_ms": 100})
    assert fr["all"]["durations_ms"] == [40, 60]
    mismatched = frame_timing_check.check(frame_timing_check.load_clips({"clips": {"x": {"frames": ["a", "b"], "durations_ms": [100, 100], "fps": 10, "duration": 0.5}}}))
    assert any(f["code"] == "duration-mismatch" for f in mismatched)
    empty = frame_timing_check.check(frame_timing_check.load_clips({"clips": {"x": {"frames": [], "fps": 12}}}))
    assert any(f["code"] == "empty" and f["severity"] == "error" for f in empty)


def test_frame_timing_cli_and_ase(tmp_path):
    json.dump(CLIPS, open(tmp_path / "c.json", "w"))
    assert frame_timing_check.main([str(tmp_path / "c.json"), "--fps", "10", "--allow-variable"]) == 1
    assert frame_timing_check.main([str(tmp_path / "c.json"), "--fps", "10", "--tolerance-ms", "25", "--allow-variable", "--report", str(tmp_path / "r.json")]) == 0
    assert frame_timing_check.main([str(tmp_path / "c.json"), "--fps", "10", "--tolerance-ms", "25", "--strict"]) == 1          # variable + single-loop are warnings
    ase = {"frames": [{"filename": "a", "frame": {"x": 0, "y": 0, "w": 1, "h": 1}, "duration": 100},
                      {"filename": "b", "frame": {"x": 1, "y": 0, "w": 1, "h": 1}, "duration": 100}],
           "meta": {"image": "s.png", "size": {"w": 2, "h": 1}, "frameTags": [{"name": "idle", "from": 0, "to": 1, "direction": "forward"}]}}
    json.dump(ase, open(tmp_path / "ase.json", "w")); assert frame_timing_check.main([str(tmp_path / "ase.json"), "--fps", "10"]) == 0
    with pytest.raises(SystemExit): frame_timing_check.load_clips({"nope": 1})


# ---------- cue-sheet
def wavs(path, x, sr=8000, bits=16): audio_tidy.write_wav(str(path), x, sr, bits)


def tone(n, amp=0.4, sr=8000, ch=1, f=220):
    t = np.arange(n) / sr; return (amp * np.sin(2 * np.pi * f * t))[:, None] * np.ones((1, ch))


def test_cue_sheet(tmp_path):
    (tmp_path / "music").mkdir(); (tmp_path / "vo").mkdir(); (tmp_path / "sfx").mkdir()
    wavs(tmp_path / "sfx" / "blip.wav", tone(int(0.2 * 8000)))                                          # oneshot
    wavs(tmp_path / "vo" / "line.wav", tone(int(2.0 * 8000), ch=1))                                      # voice (mono, 2s)
    music = tone(int(10 * 8000), ch=2, f=110); wavs(tmp_path / "music" / "theme.wav", music)
    raw = (tmp_path / "music" / "theme.wav").read_bytes(); (tmp_path / "music" / "theme.wav").write_bytes(wav_loop_meta.set_loop(raw, 1000, 70000))
    wavs(tmp_path / "sfx" / "silent.wav", np.zeros((8000, 1)))
    wavs(tmp_path / "sfx" / "hit.wav", tone(int(0.8 * 8000)))                                           # sfx
    assert cue_sheet.main([str(tmp_path), "--csv", str(tmp_path / "c.csv"), "--json", str(tmp_path / "c.json"),
                           "--rule", "vo/*=dialogue", "--rule", "music/*=music"]) == 0
    rows = {r["rel"]: r for r in json.load(open(tmp_path / "c.json"))}
    assert rows["sfx/blip.wav"]["class"] == "oneshot" and rows["sfx/blip.wav"]["bus"] == "oneshot"
    assert rows["vo/line.wav"]["class"] == "voice" and rows["vo/line.wav"]["bus"] == "dialogue"           # rule wins over class
    assert rows["music/theme.wav"]["class"] == "music" and rows["music/theme.wav"]["loop"] is True and rows["music/theme.wav"]["loop_start"] == 1000
    assert rows["sfx/silent.wav"]["class"] == "silent" and rows["sfx/hit.wav"]["class"] == "sfx"
    # a long stereo file with no smpl loop is still music, not voice
    wavs(tmp_path / "bed.wav", tone(int(12 * 8000), ch=2)); r = cue_sheet.cue(str(tmp_path / "bed.wav"), "bed.wav", [])
    assert r["class"] == "music" and r["loop"] is False
    assert "class,bus" in open(tmp_path / "c.csv").readline() or "rel" in open(tmp_path / "c.csv").readline()
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit): cue_sheet.main([str(tmp_path / "empty")])
    with pytest.raises(SystemExit): cue_sheet.main([str(tmp_path / "sfx"), "--rule", "bad"])


# ---------- level-budget
def test_level_budget(tmp_path):
    m = tmap([{"type": "tilelayer", "name": "g", "width": 4, "height": 2, "data": [1, 1, 40, 41, 40, 0, 0, 0]},
              {"type": "objectgroup", "name": "o", "objects": [
                  {"id": 1, "type": "enemy", "name": "bat"}, {"id": 2, "type": "enemy", "name": "slime"},
                  {"id": 3, "type": "pickup", "name": "coin"}, {"id": 4, "name": "spawn", "type": "spawn"},
                  {"id": 5, "type": "light", "name": "lamp", "properties": [{"name": "team", "value": "a"}]}]}])
    cfg = {"count": "type", "defaults": {"enemy": 3, "pickup": 2, "light": 0, "hazard": 10}, "ignore": ["spawn"], "tiles": {"hazard": [40, 41]},
           "maps": {"boss.json": {"enemy": 1}}}
    r = level_budget.check("level.json", m, cfg)
    by = {x["key"]: x for x in r["rows"]}
    assert by["enemy"]["count"] == 2 and by["enemy"]["status"] == "ok"
    assert by["light"]["count"] == 1 and by["light"]["status"] == "over"                                 # budget 0 means forbidden
    assert by["hazard"]["count"] == 3 and by["hazard"]["status"] == "ok"
    assert "spawn" not in by and r["under"] == []
    r2 = level_budget.check("boss.json", m, cfg); assert [x["status"] for x in r2["rows"] if x["key"] == "enemy"] == ["over"]
    # count by custom property; under budget
    cfg2 = {"count": "team", "defaults": {"a": 4, "b": 2}}
    r3 = level_budget.check("l.json", m, cfg2); by = {x["key"]: x for x in r3["rows"]}
    assert by["a"]["count"] == 1 and by["b"]["status"] == "under"
    json.dump(m, open(tmp_path / "level.json", "w")); json.dump(m, open(tmp_path / "boss.json", "w")); json.dump(cfg, open(tmp_path / "b.json", "w"))
    assert level_budget.main([str(tmp_path / "level.json"), "--budget", str(tmp_path / "b.json"), "--json", str(tmp_path / "r.json"), "--md", str(tmp_path / "r.md")]) == 1
    assert level_budget.main([str(tmp_path / "level.json"), "--budget", str(tmp_path / "b.json"), "--no-fail-on-over"]) == 0
    json.dump({"count": "type", "defaults": {"enemy": 10, "missing": 2}}, open(tmp_path / "u.json", "w"))
    assert level_budget.main([str(tmp_path / "level.json"), "--budget", str(tmp_path / "u.json"), "--fail-on-under"]) == 1
    assert "OVER" in open(tmp_path / "r.md").read() or "over" in open(tmp_path / "r.md").read()


# ---------- gltf-strip
def test_gltf_strip(tmp_path):
    # start from a real converted cube, then inject unused material, camera, extras, names and an unused accessor
    cube = tmp_path / "c.obj"
    open(cube, "w").write("o cube\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n")
    g, b = obj_to_glb.convert(str(cube)); obj_to_glb.write_glb(str(tmp_path / "c.glb"), g, b)
    js, bin_chunk = gltf_inspect.load(str(tmp_path / "c.glb"))
    js["nodes"][0]["name"] = "Root"; js["nodes"][0]["extras"] = {"note": "keep-me-not"}
    js["materials"] = (js.get("materials") or []) + [{"name": "UNUSED", "extras": {"x": 1}, "pbrMetallicRoughness": {"baseColorFactor": [1, 0, 0, 1]}}]
    js["cameras"] = [{"type": "perspective", "perspective": {"yfov": 0.7, "znear": 0.1}}]
    js["nodes"].append({"name": "Cam", "camera": 0, "translation": [0, 0, 5]})
    js["scenes"][0]["nodes"].append(1)
    js["accessors"].append({"componentType": 5126, "count": 1, "type": "SCALAR", "bufferView": 0, "byteOffset": 0})     # unused
    js["asset"]["extras"] = {"tool": "test"}
    raw, chunks, ver = None, None, 2
    gltf_strip.write(str(tmp_path / "fat.glb"), js, bin_chunk, None, 2)
    fat_size = os.path.getsize(tmp_path / "fat.glb")
    assert gltf_strip.main([str(tmp_path / "fat.glb"), "-o", str(tmp_path / "thin.glb"), "--drop-cameras", "--drop-extras", "--drop-names", "--json-report", str(tmp_path / "r.json")]) == 0
    thin, tbin = gltf_inspect.load(str(tmp_path / "thin.glb"))
    assert "cameras" not in thin and len(thin.get("materials") or []) == (1 if g.get("materials") else 0)
    assert all("name" not in n for n in thin.get("nodes", [])) and "extras" not in thin.get("asset", {}) and all("extras" not in n for n in thin.get("nodes", []))
    assert len(thin["nodes"]) == 1 and "camera" not in thin["nodes"][0]
    assert len(thin["accessors"]) == len(js["accessors"]) - 1
    assert os.path.getsize(tmp_path / "thin.glb") < fat_size
    # the mesh is still inspectable and has the same triangle count idea
    info = gltf_inspect.inspect(str(tmp_path / "thin.glb")); assert info
    rep = json.load(open(tmp_path / "r.json")); assert rep["after"]["file_bytes"] < rep["before"]["file_bytes"]
    # dropping nothing on an already compact file should still write a valid glb
    assert gltf_strip.main([str(tmp_path / "c.glb"), "-o", str(tmp_path / "c2.glb")]) == 0
    assert gltf_inspect.load(str(tmp_path / "c2.glb"))[0]["meshes"]
    # gltf JSON output + lights extension dropped
    js2, _ = gltf_inspect.load(str(tmp_path / "c.glb"))
    js2.setdefault("extensions", {})["KHR_lights_punctual"] = {"lights": [{"type": "directional"}]}
    js2.setdefault("extensionsUsed", []).append("KHR_lights_punctual")
    js2["nodes"][0].setdefault("extensions", {})["KHR_lights_punctual"] = {"light": 0}
    gltf_strip.write(str(tmp_path / "lit.glb"), js2, bin_chunk, None, 2)
    assert gltf_strip.main([str(tmp_path / "lit.glb"), "-o", str(tmp_path / "lit2.gltf"), "--drop-lights"]) == 0
    lit = json.load(open(tmp_path / "lit2.gltf")); assert "KHR_lights_punctual" not in (lit.get("extensions") or {}) and "KHR_lights_punctual" not in (lit.get("extensionsUsed") or [])
    with pytest.raises(SystemExit): gltf_strip.main([str(tmp_path / "c.obj")])


# ---------- text-wrap-bake
def test_text_wrap_bake(tmp_path):
    font = ImageFont.load_default(16); w = lambda s: font.getlength(s)
    rows = [{"id": "menu.play", "en": "Play", "de": "Spielen"},
            {"id": "greet", "en": "Hello {name}, this is a fairly long line of text that must wrap.", "de": "Hallo"}]
    # a width that wraps the English greet but not Play
    width = w("Hello 0000, this is a fairly") - 1
    baked, report = text_wrap_bake.bake(rows, ["en", "de"], font, [], width, "0000", raw=False)
    assert baked[0]["en"] == "Play" and baked[0]["de"] == "Spielen"                                     # unchanged
    assert "\n" in baked[1]["en"] and baked[1]["de"] == "Hallo"
    assert any(r["id"] == "greet" and r["lang"] == "en" and r["lines"] >= 2 for r in report) and not any(r["id"] == "menu.play" for r in report)
    # raw keeps the placeholder text and does not replace it, so the wrapped form still contains {name}
    baked_raw, _ = text_wrap_bake.bake(rows, ["en"], font, [], width, "0000", raw=True)
    assert "{name}" in baked_raw[1]["en"]
    # limits file + CLI, and refuse to overwrite the input
    csvp = tmp_path / "s.csv"; csvp.write_text('id,en,de\nmenu.play,Play,Spielen\ngreet,"Hello {name}, this is a fairly long line of text that must wrap.",Hallo\n', encoding="utf-8")
    assert text_wrap_bake.main([str(csvp), "-o", str(tmp_path / "o.csv"), "--width", str(width), "--size", "16", "--json", str(tmp_path / "r.json")]) == 0
    out = list(__import__("csv").DictReader(open(tmp_path / "o.csv", encoding="utf-8")))
    assert "\n" in out[1]["en"] and out[0]["en"] == "Play" and csvp.read_text(encoding="utf-8").count("\n") >= 2
    assert open(csvp, encoding="utf-8").read().splitlines()[2].startswith("greet,")                 # input not overwritten
    with pytest.raises(SystemExit): text_wrap_bake.main([str(csvp), "-o", str(csvp), "--width", "100"])
    with pytest.raises(SystemExit): text_wrap_bake.main([str(csvp), "-o", str(tmp_path / "x.csv")])
    # glob limits: only greet is limited
    lim = tmp_path / "lim.csv"; lim.write_text(f"id,max_px\ngreet,{int(width)}\n", encoding="utf-8")
    assert text_wrap_bake.main([str(csvp), "-o", str(tmp_path / "o2.csv"), "--limits", str(lim), "--langs", "en"]) == 0


# ---------- spritesheet-gif
def test_spritesheet_gif(tmp_path):
    # 3 frames of 8x8, trimmed in the atlas (drawn at an offset), two clips
    sheet = Image.new("RGBA", (24, 8), (0, 0, 0, 0))
    for i, c in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))):
        im = Image.new("RGBA", (6, 6), c); sheet.paste(im, (i * 8 + 1, 1))
    frames = {}
    for i, n in enumerate(("r", "g", "b")):
        frames[n] = {"frame": {"x": i * 8 + 1, "y": 1, "w": 6, "h": 6}, "spriteSourceSize": {"x": 1, "y": 1, "w": 6, "h": 6}, "sourceSize": {"w": 8, "h": 8}}
    atlas = {"frames": frames, "meta": {"image": "s.png", "size": {"w": 24, "h": 8}}}
    clips = {"clips": {"rgb": {"frames": ["r", "g", "b"], "durations_ms": [80, 100, 120], "loop": True, "duration": 0.3},
                       "rb": {"frames": ["r", "b"], "fps": 5, "loop": False}}}
    sheet.save(tmp_path / "s.png"); json.dump(atlas, open(tmp_path / "s.json", "w")); json.dump(clips, open(tmp_path / "c.json", "w"))
    # reconstruct honours the offset: the red 6x6 sits at (1,1) on an 8x8 canvas
    rec = spritesheet_gif.reconstruct(sheet, frames, "r", None); a = np.array(rec)
    assert rec.size == (8, 8) and tuple(a[1, 1]) == (255, 0, 0, 255) and a[0, 0, 3] == 0
    assert spritesheet_gif.main([str(tmp_path / "s.json"), "--clips", str(tmp_path / "c.json"), "-o", str(tmp_path / "gifs"), "--scale", "2", "--bg", "#101010"]) == 0
    im = Image.open(tmp_path / "gifs" / "rgb.gif"); assert im.size == (16, 16) and im.n_frames == 3
    # Pillow stores duration on the first frame; seek to confirm frame count and colour
    im.seek(0); p = np.array(im.convert("RGB")); assert tuple(p[3, 3]) == (255, 0, 0) or p[3, 3, 0] > 200
    im.seek(2); p = np.array(im.convert("RGB")); assert p[3, 3, 2] > 200
    assert Image.open(tmp_path / "gifs" / "rb.gif").n_frames == 2
    # single clip to a file, bounce-style sheet JSON, once
    bounce = {"frames": [{"index": i, "x": i * 8, "y": 0, "w": 8, "h": 8, "duration_ms": 50} for i in range(3)], "total_ms": 150}
    # need an image whose frames are at 0,8,16 - our sheet already is, but content is inset; still valid 8x8 cells
    json.dump({**bounce, "meta": {"image": "s.png"}}, open(tmp_path / "bounce.json", "w"))
    # bounce frames use x=0,8,16 full cells; write a dedicated image
    full = Image.new("RGBA", (24, 8), (0, 0, 0, 0))
    for i, c in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))): full.paste(Image.new("RGBA", (8, 8), c), (i * 8, 0))
    full.save(tmp_path / "bounce.png"); json.dump(bounce, open(tmp_path / "bounce.json", "w"))
    assert spritesheet_gif.main([str(tmp_path / "bounce.json"), "--image", str(tmp_path / "bounce.png"), "-o", str(tmp_path / "one.gif"), "--once"]) == 0
    g = Image.open(tmp_path / "one.gif"); assert g.size == (8, 8) and g.n_frames == 3
    assert spritesheet_gif.main([str(tmp_path / "s.json"), "--clips", str(tmp_path / "c.json"), "--clip", "rb", "-o", str(tmp_path / "only.gif")]) == 0
    with pytest.raises(SystemExit): spritesheet_gif.main([str(tmp_path / "s.json"), "--clips", str(tmp_path / "c.json"), "--clip", "nope", "-o", str(tmp_path / "x.gif")])
    with pytest.raises(SystemExit): spritesheet_gif.main([str(tmp_path / "s.json"), "-o", str(tmp_path / "x.gif")])


# tighten the sloppy GIF duration assert above in a follow-up if needed
