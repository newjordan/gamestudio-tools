from gst_errors import GstInputError
import base64, csv, json, os, struct, wave, zlib
import numpy as np
import pytest
from PIL import Image
import lut_tool, sprite_pivot, glb_diff, wav_loop_meta, tmx_to_json, game_data_lint, ldtk_to_csv, atlas_validate, font_check
import atlas_pack, glb_lod


# ---------- lut-tool
def test_lut_identity_apply_and_cube(tmp_path):
    lut = lut_tool.identity(8)
    img = Image.fromarray(np.random.default_rng(0).integers(0, 256, (16, 16, 3), dtype=np.uint8)).convert("RGBA")
    out = lut_tool.apply(img, lut)
    assert np.abs(np.array(out).astype(int) - np.array(img).astype(int)).max() <= 1       # identity LUT is a no-op (trilinear rounding)
    strip = lut_tool.to_strip(lut); assert strip.size == (64, 8)
    assert np.allclose(lut_tool.from_strip(strip), lut, atol=1 / 255 + 1e-6)
    inv = lut_tool.make(8, brightness=0.2)
    assert np.array(lut_tool.apply(Image.new("RGBA", (2, 2), (100, 100, 100, 255)), inv))[0, 0, 0] > 130
    gray = lut_tool.make(8, saturation=0)
    px = np.array(lut_tool.apply(Image.new("RGBA", (1, 1), (255, 0, 0, 255)), gray))[0, 0]
    assert px[0] == px[1] == px[2]
    lut_tool.write_cube(str(tmp_path / "a.cube"), inv)
    back = lut_tool.read_cube(str(tmp_path / "a.cube")); assert back.shape == inv.shape and np.allclose(back, inv, atol=1e-5)
    # alpha is preserved
    a = Image.new("RGBA", (2, 2), (10, 20, 30, 77)); assert np.array(lut_tool.apply(a, inv))[0, 0, 3] == 77


def test_lut_cli(tmp_path):
    p = str(tmp_path / "l.png")
    lut_tool.main(["make", "--size", "8", "--contrast", "1.3", "--tint", "#ff8800", "--tint-amount", "0.2", "-o", p]); assert Image.open(p).size == (64, 8)
    src = tmp_path / "s.png"; Image.new("RGBA", (4, 4), (90, 120, 200, 255)).save(src)
    lut_tool.main(["apply", str(src), "--lut", p, "-o", str(tmp_path / "o.png")]); assert (tmp_path / "o.png").exists()
    lut_tool.main(["to-cube", p, "-o", str(tmp_path / "c.cube")]); lut_tool.main(["from-cube", str(tmp_path / "c.cube"), "-o", str(tmp_path / "r.png")])
    assert Image.open(tmp_path / "r.png").size == (64, 8)


# ---------- sprite-pivot
def test_sprite_pivot(tmp_path):
    img = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(4, 10):
        for y in range(2, 14): img.putpixel((x, y), (255, 0, 0, 255))
    (p, bb) = sprite_pivot.frame_pivot(img, "feet"); assert p == (7.0, 14.0) and bb == (4, 2, 10, 14)
    assert sprite_pivot.frame_pivot(img, "center")[0] == (7.0, 8.0)
    assert sprite_pivot.frame_pivot(img, "top-left")[0] == (4.0, 2.0)
    assert sprite_pivot.frame_pivot(img, "centroid")[0] == (7.0, 8.0)
    e = sprite_pivot.export("a", (20, 20), (7.0, 14.0), bb)
    assert e["unity_pivot"] == [0.35, 0.3] and e["godot_offset"] == [3.0, -4.0]
    # animation alignment: all frames get the same (median) pivot
    img2 = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(6, 12):
        for y in range(2, 16): img2.putpixel((x, y), (0, 255, 0, 255))
    img.save(tmp_path / "f1.png"); img2.save(tmp_path / "f2.png")
    r = sprite_pivot.process([str(tmp_path / "f1.png"), str(tmp_path / "f2.png")], "feet", True)
    assert r[0]["pivot_px"] == r[1]["pivot_px"] == [8.0, 15.0]
    r = sprite_pivot.process([str(tmp_path / "f1.png"), str(tmp_path / "f2.png")], "feet", False); assert r[0]["pivot_px"] != r[1]["pivot_px"]
    sprite_pivot.main([str(tmp_path), "--mode", "feet", "-o", str(tmp_path / "p.json")]); assert len(json.load(open(tmp_path / "p.json"))["frames"]) == 2
    empty = Image.new("RGBA", (10, 6)); assert sprite_pivot.frame_pivot(empty)[0] == (5.0, 3.0)


# ---------- glb-diff
def test_glb_diff(tmp_path):
    from test_batch2 import make_grid_glb
    a = tmp_path / "a.glb"; make_grid_glb(str(a))
    glb_lod.simplify(str(a), 0.3, str(tmp_path / "b.glb"))
    d = glb_diff.compare(glb_diff.summarize(str(a)), glb_diff.summarize(str(tmp_path / "b.glb")))
    assert d["tris"][1] < d["tris"][0] * 0.5 and d["tris"][2] < -50 and d["bytes"][2] < 0
    same = glb_diff.compare(glb_diff.summarize(str(a)), glb_diff.summarize(str(a))); assert same["tris"][2] == 0 and not same["meshes"]["changed"]
    assert glb_diff.main([str(a), str(tmp_path / "b.glb"), "--max-tri-increase", "5", "--json", str(tmp_path / "d.json")]) == 0   # decrease passes
    assert glb_diff.main([str(tmp_path / "b.glb"), str(a), "--max-tri-increase", "5"]) == 1                                        # big increase fails
    assert glb_diff.main([str(tmp_path / "b.glb"), str(a), "--max-size-increase", "10"]) == 1
    assert json.load(open(tmp_path / "d.json"))


# ---------- wav-loop-meta
def _wav(path, n=4000, sr=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.sin(np.arange(n) * 0.1) * 8000).astype("<i2").tobytes())


def test_wav_loop_meta(tmp_path):
    p = tmp_path / "m.wav"; _wav(p)
    raw = open(p, "rb").read(); out = wav_loop_meta.set_loop(raw, 500, 3000)
    assert wav_loop_meta.read_loops(out) == [{"start": 500, "end": 3000, "play_count": 0}]
    open(tmp_path / "l.wav", "wb").write(out)
    with wave.open(str(tmp_path / "l.wav")) as w: assert w.getnframes() == 4000 and w.getframerate() == 8000      # still a valid wav
    assert struct.unpack_from("<I", out, 4)[0] == len(out) - 8                                                      # RIFF size is consistent
    again = wav_loop_meta.set_loop(out, 100, 200); assert wav_loop_meta.read_loops(again) == [{"start": 100, "end": 200, "play_count": 0}]
    assert wav_loop_meta.read_loops(wav_loop_meta.clear(out)) == []
    with pytest.raises(SystemExit): wav_loop_meta.set_loop(raw, 10, 5000)
    json.dump({"m.wav": {"start": 100, "end": 2100}}, open(tmp_path / "lp.json", "w"))
    wav_loop_meta.main(["from-json", str(tmp_path / "lp.json"), "--dir", str(tmp_path), "-o", str(tmp_path / "o")])
    assert wav_loop_meta.read_loops(open(tmp_path / "o" / "m.wav", "rb").read())[0]["end"] == 2099
    # odd-sized chunk padding is preserved
    odd = raw[:4] + struct.pack("<I", len(raw) - 8 + 8) + raw[8:] + b"LIST" + struct.pack("<I", 3) + b"abc\0"
    r = wav_loop_meta.set_loop(odd, 10, 20); assert wav_loop_meta.read_loops(r)[0]["start"] == 10 and b"abc" in r


# ---------- tmx-to-json
TMX = """<?xml version="1.0"?>
<map version="1.10" orientation="orthogonal" renderorder="right-down" width="3" height="2" tilewidth="16" tileheight="16" nextlayerid="4" nextobjectid="3">
 <properties><property name="biome" value="cave"/><property name="depth" type="int" value="3"/></properties>
 <tileset firstgid="1" name="t" tilewidth="16" tileheight="16" tilecount="4" columns="2"><image source="t.png" width="32" height="32"/></tileset>
 <tileset firstgid="5" source="ext.tsx"/>
 <layer id="1" name="ground" width="3" height="2"><data encoding="csv">
1,2,3,
4,0,2147483649
</data></layer>
 <layer id="2" name="packed" width="3" height="2"><data encoding="base64" compression="zlib">%s</data></layer>
 <objectgroup id="3" name="things"><object id="1" name="spawn" type="Spawn" x="16" y="32.5"><point/></object>
  <object id="2" x="0" y="0" width="16" height="8"><properties><property name="solid" type="bool" value="true"/></properties></object>
  <object id="5" x="4" y="4"><polygon points="0,0 10,0 5,8"/></object></objectgroup>
</map>"""


def test_tmx_to_json(tmp_path):
    ids = [1, 2, 3, 4, 0, 6]
    packed = base64.b64encode(zlib.compress(struct.pack("<6I", *ids))).decode()
    p = tmp_path / "m.tmx"; p.write_text(TMX % packed)
    m = tmx_to_json.convert(str(p))
    assert (m["width"], m["height"], m["tilewidth"]) == (3, 2, 16) and m["layers"][0]["data"] == [1, 2, 3, 4, 0, 2147483649]
    assert m["layers"][1]["data"] == ids
    assert m["tilesets"][0]["image"] == "t.png" and m["tilesets"][0]["columns"] == 2 and m["tilesets"][1] == {"firstgid": 5, "source": "ext.tsx"}
    assert {x["name"]: x["value"] for x in m["properties"]} == {"biome": "cave", "depth": 3}
    o = m["layers"][2]["objects"]; assert o[0]["point"] and o[0]["y"] == 32.5 and o[0]["x"] == 16 and isinstance(o[0]["x"], int)
    assert o[1]["properties"][0]["value"] is True and o[2]["polygon"][2] == {"x": 5, "y": 8}
    tmx_to_json.main([str(p), "-o", str(tmp_path / "out.json")]); assert json.load(open(tmp_path / "out.json"))["layers"][0]["name"] == "ground"
    # round-trips through our other Tiled tool
    gz = base64.b64encode(__import__("gzip").compress(struct.pack("<6I", *ids))).decode()
    p2 = tmp_path / "g.tmx"; p2.write_text((TMX % gz).replace('compression="zlib"', 'compression="gzip"'))
    assert tmx_to_json.convert(str(p2))["layers"][1]["data"] == ids
    p3 = tmp_path / "z.tmx"; p3.write_text((TMX % gz).replace('compression="zlib"', 'compression="zstd"'))
    with pytest.raises(GstInputError): tmx_to_json.convert(str(p3))   # gzip bytes labelled zstd: not a zstd frame


# ---------- game-data-lint
def test_game_data_lint(tmp_path):
    (tmp_path / "items.csv").write_text("id,price,rarity,icon\nsword,10,common,s.png\nbow,-5,rare,\nsword,3,epic,x\nwand,abc,legendary,\nBad Id,1,common,\n")
    json.dump([{"id": "orc", "hp": 30, "drop": "sword,wand"}, {"id": "bat", "hp": 400, "drop": "ghost"}, {"id": "rat", "drop": "bow", "hpp": 1}], open(tmp_path / "enemies.json", "w"))
    schema = {"tables": {
        "items": {"file": "items.csv", "key": "id", "fields": {"id": {"type": "str", "pattern": "^[a-z_]+$", "unique": True}, "price": {"type": "int", "min": 0},
                  "rarity": {"type": "enum", "values": ["common", "rare", "epic"]}, "icon": {"type": "str", "required": False}}},
        "enemies": {"file": "enemies.json", "fields": {"id": {"type": "str"}, "hp": {"type": "int", "min": 1, "max": 100}, "drop": {"type": "ref", "table": "items", "list": ","}}}}}
    r = game_data_lint.lint(schema, str(tmp_path))
    msgs = [(x["table"], x["row"], x["field"], x["level"]) for x in r]
    assert ("items", 2, "price", "error") in msgs                      # < min
    assert ("items", 3, "id", "error") in msgs                         # duplicate
    assert ("items", 4, "price", "error") in msgs and ("items", 4, "rarity", "error") in msgs
    assert ("items", 5, "id", "error") in msgs                         # pattern
    assert ("enemies", 2, "hp", "error") in msgs and ("enemies", 2, "drop", "error") in msgs   # max and bad ref
    assert ("enemies", 3, "hp", "error") in msgs                       # required missing
    assert ("enemies", 3, "hpp", "warn") in msgs
    assert not [x for x in r if x["table"] == "enemies" and x["row"] == 1]  # orc is clean (refs to existing items in a list)
    assert not [x for x in r if x["table"] == "items" and x["row"] == 1]
    json.dump(schema, open(tmp_path / "s.json", "w")); assert game_data_lint.main([str(tmp_path / "s.json")]) == 1
    (tmp_path / "items.csv").write_text("id,price,rarity,icon\nsword,1,common,\nwand,2,rare,\nbow,3,epic,\n")
    json.dump([{"id": "orc", "hp": 30, "drop": "sword,wand"}], open(tmp_path / "enemies.json", "w"))
    assert game_data_lint.main([str(tmp_path / "s.json")]) == 0
    json.dump([{"id": "orc", "hp": 30, "drop": "sword", "extra": 1}], open(tmp_path / "enemies.json", "w"))
    assert game_data_lint.main([str(tmp_path / "s.json")]) == 0 and game_data_lint.main([str(tmp_path / "s.json"), "--strict"]) == 1
    assert game_data_lint.parse("1.0", "float") == 1.0 and game_data_lint.parse("yes", "bool") is True
    with pytest.raises(ValueError): game_data_lint.parse(1.5, "int")


# ---------- ldtk-to-csv
def _ldtk():
    ig = [0, 1, 1, 0, 2, 0]
    tiles = [{"px": [0, 0], "src": [0, 0], "f": 0, "t": 4}, {"px": [32, 16], "src": [16, 0], "f": 0, "t": 7}]
    lay = [{"__identifier": "Walls", "__type": "IntGrid", "__cWid": 3, "__cHei": 2, "__gridSize": 16, "intGridCsv": ig, "gridTiles": [], "autoLayerTiles": []},
           {"__identifier": "Deco", "__type": "Tiles", "__cWid": 3, "__cHei": 2, "__gridSize": 16, "gridTiles": tiles, "autoLayerTiles": []},
           {"__identifier": "Things", "__type": "Entities", "__cWid": 3, "__cHei": 2, "__gridSize": 16,
            "entityInstances": [{"__identifier": "Chest", "px": [16, 16], "width": 16, "height": 16, "fieldInstances": [{"__identifier": "loot", "__value": "gold"}]}]}]
    return {"levels": [{"identifier": "L0", "layerInstances": lay}, {"identifier": "L1", "layerInstances": None, "externalRelPath": "L1.ldtkl"}]}


def test_ldtk_to_csv(tmp_path):
    proj = _ldtk(); lv = proj["levels"][0]["layerInstances"]
    assert ldtk_to_csv.layer_grid(lv[0]) == [[0, 1, 1], [0, 2, 0]]
    assert ldtk_to_csv.layer_grid(lv[1]) == [[5, 0, 0], [0, 0, 8]]
    assert ldtk_to_csv.entities(lv)[0]["x"] == 16 and json.loads(ldtk_to_csv.entities(lv)[0]["fields"]) == {"loot": "gold"}
    json.dump(proj, open(tmp_path / "p.ldtk", "w"))
    json.dump({"identifier": "L1", "layerInstances": [lv[0]]}, open(tmp_path / "L1.ldtkl", "w"))
    ldtk_to_csv.main([str(tmp_path / "p.ldtk"), "-o", str(tmp_path / "o"), "--tiled"])
    files = sorted(os.listdir(tmp_path / "o")); assert "L0_Walls.csv" in files and "L0_Deco.csv" in files and "L0_entities.csv" in files and "L1_Walls.csv" in files and "L0.json" in files
    assert list(csv.reader(open(tmp_path / "o" / "L0_Walls.csv")))[1] == ["0", "2", "0"]
    m = json.load(open(tmp_path / "o" / "L0.json")); assert m["layers"][1]["data"] == [5, 0, 0, 0, 0, 8] and m["tilewidth"] == 16


# ---------- atlas-validate
def test_atlas_validate(tmp_path):
    for i, c in enumerate([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]):
        Image.new("RGBA", (10 + i, 12), c).save(tmp_path / f"s{i}.png")
    atlas, frames = atlas_pack.pack([str(tmp_path / f"s{i}.png") for i in range(3)], padding=2)
    meta = {"frames": frames, "meta": {"image": "a.png"}}
    assert [x for x in atlas_validate.validate(meta, atlas, padding=1) if x["level"] == "error"] == []
    bad = json.loads(json.dumps(meta))
    bad["frames"]["s0"]["frame"]["x"] = bad["frames"]["s1"]["frame"]["x"]; bad["frames"]["s0"]["frame"]["y"] = bad["frames"]["s1"]["frame"]["y"]
    assert any("overlaps" in x["msg"] for x in atlas_validate.validate(bad, atlas))
    # sprite-sheet-optimize stores a repeated frame once and points the copy at it with alias_of
    shared = json.loads(json.dumps(meta))
    shared["frames"]["s0"]["frame"] = dict(shared["frames"]["s1"]["frame"])
    shared["frames"]["s0"]["alias_of"] = "s1"
    assert not any("overlaps" in x["msg"] for x in atlas_validate.validate(shared, atlas))
    sib = json.loads(json.dumps(meta))
    sib["frames"]["s0"]["frame"] = dict(sib["frames"]["s2"]["frame"])
    sib["frames"]["s1"]["frame"] = dict(sib["frames"]["s2"]["frame"])
    sib["frames"]["s0"]["alias_of"] = "s2"
    sib["frames"]["s1"]["alias_of"] = "s2"
    assert not any("overlaps" in x["msg"] for x in atlas_validate.validate(sib, atlas))
    bare = json.loads(json.dumps(shared)); del bare["frames"]["s0"]["alias_of"]
    assert any("overlaps" in x["msg"] for x in atlas_validate.validate(bare, atlas))
    bad = json.loads(json.dumps(meta)); bad["frames"]["s2"]["frame"]["x"] = atlas.width - 3
    assert any("outside" in x["msg"] for x in atlas_validate.validate(bad, atlas))
    # tight frames -> padding warning; transparent -> warning; array layout works
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); img.paste(Image.new("RGBA", (10, 10), (1, 1, 1, 255)), (0, 0)); img.paste(Image.new("RGBA", (10, 10), (1, 1, 1, 255)), (10, 0))
    arr = {"frames": [{"filename": "a", "frame": {"x": 0, "y": 0, "w": 10, "h": 10}}, {"filename": "b", "frame": {"x": 10, "y": 0, "w": 10, "h": 10}}, {"filename": "c", "frame": {"x": 40, "y": 40, "w": 5, "h": 5}}, {"filename": "a", "frame": {"x": 30, "y": 30, "w": 2, "h": 2}}]}
    r = atlas_validate.validate(arr, img, padding=2); t = " | ".join(x["msg"] for x in r)
    assert "only 0px from b" in t and "fully transparent" in t and "duplicate frame name" in t
    odd = atlas_validate.validate({"frames": {}}, Image.new("RGBA", (100, 64))); assert any("power-of-two" in x["msg"] for x in odd)
    trim = {"frames": {"t": {"frame": {"x": 0, "y": 0, "w": 10, "h": 10}, "spriteSourceSize": {"x": 8, "y": 0, "w": 10, "h": 10}, "sourceSize": {"w": 12, "h": 12}}}}
    assert any("sourceSize" in x["msg"] for x in atlas_validate.validate(trim, img))
    atlas.save(tmp_path / "a.png"); json.dump(meta, open(tmp_path / "a.json", "w"))
    assert atlas_validate.main([str(tmp_path / "a.json")]) == 0
    json.dump(bad, open(tmp_path / "b.json", "w")); assert atlas_validate.main([str(tmp_path / "b.json"), "--image", str(tmp_path / "a.png")]) == 1


# ---------- font-check
def _font_path():
    import glob
    for g in ("/usr/share/fonts/**/DejaVuSans.ttf", "/usr/share/fonts/**/*.ttf"):
        f = glob.glob(g, recursive=True)
        if f: return f[0]
    return None


def test_font_check(tmp_path):
    t = tmp_path / "s.txt"; t.write_text("Hello world!\nplain ascii {name}\n")
    chars = "Helo rd!pain sc{}ne"                    # no w, no m
    fnt = tmp_path / "f.fnt"; fnt.write_text("info face=x size=16\n" + "".join(f"char id={ord(c)} x=0 y=0\n" for c in chars))
    cnt = font_check.text_chars([str(t)])
    assert font_check.check(cnt, [str(fnt)])[str(fnt)] == ["m", "w"] and cnt["l"] == 4
    assert font_check.main([str(t), "--font", str(fnt)]) == 1
    assert font_check.main([str(t), "--font", str(fnt), "--ignore", "wm"]) == 0
    u = tmp_path / "u.txt"; u.write_text("abc \u00e9 \u4e2d \n")
    assert font_check.main([str(u), "--font", str(fnt)]) == 1
    fp = _font_path()
    if fp and font_check.TTFont is not None:
        miss = font_check.check(font_check.text_chars([str(u)]), [fp])[fp]
        assert "\u00e9" not in miss                     # Latin e-acute is in any real TTF
        assert font_check.check(["\ue000", "A"], [fp])[fp] == ["\ue000"]
        assert font_check.main([str(t), "--font", fp, "--json", str(tmp_path / "r.json")]) == 0
        assert json.load(open(tmp_path / "r.json"))[fp] == []
