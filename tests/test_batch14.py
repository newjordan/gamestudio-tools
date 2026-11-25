import base64, json, os, struct, wave, zlib
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from gst_errors import GstInputError
from PIL import Image
import audio_tidy, tilemap_stats, map_diff, map_clean, level_budget, tile_anim_gif, tile_preview
import wav_trim, tmx_layer_export, map_merge, loc_placeholder_lint, particle_preview, sprite_angles, material_audit, room_graph


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
DEJA = os.path.join(SAMPLES, "b9", "DejaVuSans-subset.ttf")


def tmap(layers, **kw):
    m = {"type": "map", "width": 4, "height": 2, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal",
         "tilesets": [{"name": "ground", "firstgid": 1, "tilecount": 10, "image": "tileset.png", "tilewidth": 16, "tileheight": 16, "columns": 4}],
         "layers": layers}
    m.update(kw); return m


def write_wav(path, samples, sr=22050, ch=1):
    x = np.asarray(samples, np.float32)
    if x.ndim == 1: x = x[:, None]
    if ch == 2 and x.shape[1] == 1: x = np.repeat(x, 2, 1)
    audio_tidy.write_wav(str(path), x, sr, bits=16)


# ---------- gap closures
def test_encoded_and_tsx(tmp_path):
    # valid zlib data is decoded; map-clean writes plain arrays; level-budget counts those tiles
    raw = struct.pack("<8I", 1, 1, 2, 0, 1, 0, 0, 0)
    enc = base64.b64encode(zlib.compress(raw)).decode()
    m = tmap([{"type": "tilelayer", "name": "g", "width": 4, "height": 2, "encoding": "base64", "compression": "zlib", "data": enc},
              {"type": "objectgroup", "name": "obj", "objects": [{"id": 1, "name": "bat", "type": "enemy", "x": 0, "y": 0}]}])
    s = tilemap_stats.stats_one("e.json", m)
    assert s["tile_layers"][0]["unique_tiles"] == 2 and s["tile_layers"][0]["empty"] == 4
    json.dump(m, open(tmp_path / "enc.json", "w"))
    json.dump({"count": "type", "defaults": {"enemy": 3}, "tiles": {"hazard": [2]}}, open(tmp_path / "bud.json", "w"))
    assert level_budget.main([str(tmp_path / "enc.json"), "--budget", str(tmp_path / "bud.json"), "--json", str(tmp_path / "b.json")]) == 0
    rows = json.load(open(tmp_path / "b.json"))[0]
    assert rows["counts"]["enemy"] == 1 and rows["counts"]["hazard"] == 1
    assert map_clean.main([str(tmp_path / "enc.json"), "-o", str(tmp_path / "clean.json")]) == 0
    cleaned = json.load(open(tmp_path / "clean.json"))
    assert cleaned["layers"][0]["data"] == [1, 1, 2, 0, 1, 0, 0, 0] and "encoding" not in cleaned["layers"][0]
    # bytes that are not a zstd frame are a typed error
    with pytest.raises(GstInputError):
        map_diff.decode_tile_data("aaaa", encoding="base64", compression="zstd", layer_name="z")
    # external .tsx: animation frames load and a per-tile GIF is written
    sheet = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for i, c in enumerate([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]):
        sheet.paste(Image.new("RGBA", (16, 16), c), (i * 16, 0))
    sheet.save(tmp_path / "tileset.png")
    (tmp_path / "anim.tsx").write_text("""<?xml version="1.0"?>
<tileset name="water" tilewidth="16" tileheight="16" tilecount="4" columns="4">
 <image source="tileset.png" width="64" height="16"/>
 <tile id="0"><animation>
  <frame tileid="0" duration="100"/><frame tileid="1" duration="100"/>
  <frame tileid="2" duration="100"/><frame tileid="3" duration="100"/>
 </animation></tile>
</tileset>
""")
    mmap = tmap([{"type": "tilelayer", "name": "g", "width": 4, "height": 2, "data": [1, 1, 0, 0, 0, 0, 0, 0]}],
                tilesets=[{"firstgid": 1, "source": "anim.tsx"}])
    json.dump(mmap, open(tmp_path / "map.json", "w"))
    assert tile_anim_gif.main([str(tmp_path / "anim.tsx"), "-o", str(tmp_path / "fromtsx"), "--scale", "2"]) == 0
    assert (tmp_path / "fromtsx" / "water_0.gif").is_file()
    assert tile_anim_gif.main([str(tmp_path / "map.json"), "-o", str(tmp_path / "frommap"), "--tick-ms", "100", "--duration-ms", "200"]) == 0
    assert (tmp_path / "frommap" / "water_0.gif").is_file() and (tmp_path / "frommap" / "map.gif").is_file()
    # tile-preview resolves the external image
    im, n = tile_preview.render(json.load(open(tmp_path / "map.json")), None, str(tmp_path))
    assert n >= 1 and im.size == (64, 32)


def test_wav_trim(tmp_path):
    sr = 8000
    # 80 ms silence, 100 ms tone, 80 ms silence
    z = int(0.08 * sr); t = int(0.10 * sr)
    tone = 0.4 * np.sin(2 * np.pi * 440 * np.arange(t) / sr)
    samples = np.concatenate([np.zeros(z), tone, np.zeros(z)])
    src = tmp_path / "pad.wav"; write_wav(src, samples, sr)
    silent = tmp_path / "quiet.wav"; write_wav(silent, np.zeros(sr // 10), sr)
    assert wav_trim.main([str(src), str(silent), "--outdir", str(tmp_path / "out"), "--thresh-db", "-60", "--pad-ms", "10",
                          "--json", str(tmp_path / "r.json")]) == 0
    rows = json.load(open(tmp_path / "r.json"))
    assert rows[0]["status"] == "trimmed" and rows[0]["after_s"] < rows[0]["before_s"]
    assert rows[1]["status"] == "silent" and rows[1]["out"] is None
    y, nsr = audio_tidy.read_wav(str(tmp_path / "out" / "pad.wav")); assert nsr == sr and len(y) < len(samples)
    with pytest.raises(SystemExit): wav_trim.main([str(src)])


def test_tmx_layer_export_and_merge(tmp_path):
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    sheet.paste(Image.new("RGBA", (16, 16), (255, 0, 0, 255)), (0, 0))
    sheet.paste(Image.new("RGBA", (16, 16), (0, 0, 255, 255)), (16, 0))
    sheet.save(tmp_path / "tileset.png")
    a = tmap([{"type": "tilelayer", "name": "base", "width": 4, "height": 2, "data": [1, 1, 0, 0, 1, 0, 0, 0]},
              {"type": "tilelayer", "name": "hid", "width": 4, "height": 2, "visible": False, "data": [2, 0, 0, 0, 0, 0, 0, 0]},
              {"type": "objectgroup", "name": "obj", "objects": [{"id": 1, "name": "door", "type": "door", "x": 8, "y": 8, "properties": [{"name": "target", "value": "b"}]}]}],
             tilesets=[{"name": "t", "firstgid": 1, "tilecount": 2, "image": "tileset.png", "tilewidth": 16, "tileheight": 16, "columns": 2, "imagewidth": 32, "imageheight": 16}])
    b = tmap([{"type": "tilelayer", "name": "base", "width": 4, "height": 2, "data": [2, 2, 2, 2, 0, 0, 0, 0]},
              {"type": "objectgroup", "name": "obj", "objects": [{"id": 1, "name": "door", "type": "door", "x": 0, "y": 0, "properties": [{"name": "target", "value": "a"}]}]}],
             tilesets=[{"name": "t", "firstgid": 1, "tilecount": 2, "image": "tileset.png", "tilewidth": 16, "tileheight": 16, "columns": 2}])
    json.dump(a, open(tmp_path / "a.json", "w")); json.dump(b, open(tmp_path / "b.json", "w"))
    assert tmx_layer_export.main([str(tmp_path / "a.json"), "-o", str(tmp_path / "layers"), "--include-hidden"]) == 0
    assert (tmp_path / "layers" / "composite.png").is_file()
    names = sorted(p.name for p in (tmp_path / "layers").iterdir())
    assert any(n.endswith("_base.png") for n in names) and any(n.endswith("_hid.png") for n in names)
    assert map_merge.main([str(tmp_path / "a.json"), str(tmp_path / "b.json"), "-o", str(tmp_path / "merged.json"),
                           "--offset", "0,0", "--offset", "4,0", "--prefix", "A_", "--prefix", "B_", "--pretty"]) == 0
    m = json.load(open(tmp_path / "merged.json"))
    assert m["width"] == 8 and m["height"] == 2
    # A_base first 4 cells, B_base starts at x=4
    base_a = next(l for l in m["layers"] if l["name"] == "A_base")
    base_b = next(l for l in m["layers"] if l["name"] == "B_base")
    assert base_a["data"][:4] == [1, 1, 0, 0] and base_b["data"][4:8] == [2, 2, 2, 2]
    assert len(m["tilesets"]) == 1  # same image reused


def test_loc_placeholder_lint(tmp_path):
    # greet in samples has {nam} typo in de
    csv_ok = "id,en,fr\nhi,Hello {name} %d,Bonjour {name} %d\n"
    csv_bad = "id,en,de\ngreet,Hello {name} %d,Hallo {nam} %s\n"
    (tmp_path / "ok.csv").write_text(csv_ok, encoding="utf-8")
    (tmp_path / "bad.csv").write_text(csv_bad, encoding="utf-8")
    assert loc_placeholder_lint.main([str(tmp_path / "ok.csv")]) == 0
    assert loc_placeholder_lint.main([str(tmp_path / "bad.csv"), "--json", str(tmp_path / "j.json")]) == 1
    issues = json.load(open(tmp_path / "j.json"))
    msgs = " ".join(i["msg"] for i in issues)
    assert "named" in msgs and "printf" in msgs
    # also the kit sample strings.csv (de typo + missing fr on quit is skipped)
    sample = os.path.join(SAMPLES, "strings.csv")
    if os.path.isfile(sample):
        assert loc_placeholder_lint.main([sample]) == 1


def test_particle_and_angles(tmp_path):
    assert particle_preview.main(["-o", str(tmp_path / "burst.gif"), "--width", "64", "--height", "64", "--count", "12",
                                  "--frames", "8", "--fps", "8", "--seed", "2", "--png", str(tmp_path / "p0.png")]) == 0
    im = Image.open(tmp_path / "burst.gif")
    assert im.size == (64, 64) and getattr(im, "n_frames", 1) == 8
    assert Image.open(tmp_path / "p0.png").size == (64, 64)
    spr = Image.new("RGBA", (8, 12), (0, 0, 0, 0)); spr.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (0, 0))
    spr.save(tmp_path / "hero.png")
    assert sprite_angles.main([str(tmp_path / "hero.png"), "-o", str(tmp_path / "hero_8.png"), "--angles", "8"]) == 0
    sheet = Image.open(tmp_path / "hero_8.png"); atlas = json.load(open(tmp_path / "hero_8.json"))
    assert len(atlas["frames"]) == 8 and sheet.size[0] >= 8 and "hero_000" in atlas["frames"]
    assert atlas["meta"]["angles"][1] == 45
    # 16-dir, ccw
    assert sprite_angles.main([str(tmp_path / "hero.png"), "-o", str(tmp_path / "hero_16.png"), "--angles", "16", "--ccw"]) == 0
    assert len(json.load(open(tmp_path / "hero_16.json"))["frames"]) == 16


def test_material_audit(tmp_path):
    # self-contained (the release tarball does not include samples/)
    ok = {"asset": {"version": "2.0"},
          "materials": [{"name": "m", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
          "textures": [{"source": 0}],
          "images": [{"uri": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}],
          "meshes": [], "buffers": []}
    json.dump(ok, open(tmp_path / "ok.gltf", "w"))
    assert material_audit.main([str(tmp_path / "ok.gltf"), "--json", str(tmp_path / "a.json")]) == 0
    data = json.load(open(tmp_path / "a.json"))
    assert data["files"][0]["materials"] and "m" in data["unique_materials"]

    # a tiny glTF with a missing external uri
    gltf = {"asset": {"version": "2.0"}, "materials": [{"name": "missing", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
            "textures": [{"source": 0}], "images": [{"uri": "no-such-texture.png"}], "meshes": [], "buffers": []}
    json.dump(gltf, open(tmp_path / "miss.gltf", "w"))
    assert material_audit.main([str(tmp_path / "miss.gltf"), "--fail-on-missing"]) == 1


def test_room_graph(tmp_path):
    # two maps, doors point at each other; a third unreachable room on map c
    def room_map(name, doors, rooms=None):
        objs = []
        for i, d in enumerate(doors, 1):
            o = {"id": i, "name": d.get("name", "d"), "type": "door", "x": d.get("x", 0), "y": d.get("y", 0), "width": 8, "height": 8}
            if "target" in d: o["properties"] = [{"name": "target", "value": d["target"]}]
            objs.append(o)
        if rooms:
            for j, r in enumerate(rooms, 10):
                objs.append({"id": j, "name": r["name"], "type": "room", "x": r["x"], "y": r["y"], "width": r["w"], "height": r["h"]})
        return tmap([{"type": "objectgroup", "name": "obj", "objects": objs}], width=8, height=8)
    json.dump(room_map("a", [{"name": "toB", "target": "b"}]), open(tmp_path / "a.json", "w"))
    json.dump(room_map("b", [{"name": "toA", "target": "a"}]), open(tmp_path / "b.json", "w"))
    json.dump(room_map("c", []), open(tmp_path / "c.json", "w"))
    assert room_graph.main([str(tmp_path / "a.json"), str(tmp_path / "b.json"), str(tmp_path / "c.json"),
                            "--mermaid", str(tmp_path / "g.mmd"), "--dot", str(tmp_path / "g.dot"),
                            "--json", str(tmp_path / "g.json"), "--start", "a", "--fail-on-unreachable"]) == 1
    g = json.load(open(tmp_path / "g.json"))
    assert set(g["rooms"]) >= {"a", "b", "c"} and "c" in g["unreachable"] and "b" not in g["unreachable"]
    assert "flowchart" in open(tmp_path / "g.mmd").read() and "digraph" in open(tmp_path / "g.dot").read()
