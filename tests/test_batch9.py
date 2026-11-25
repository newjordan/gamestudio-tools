import glob, json, os, wave
import numpy as np
import pytest
from PIL import Image
import tile_preview, sfx_bank, asset_rename, lit_preview, drop_sim, level_curve, font_subset, colorblind_sim
import audio_tidy


# ---------- tile-preview
def tileset_png(path):
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    cols = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    for i, c in enumerate(cols): im.paste(Image.new("RGBA", (16, 16), c), ((i % 2) * 16, (i // 2) * 16))
    im.putpixel((1, 1), (255, 255, 255, 255))                       # marker in the top-left of tile 0 (to see flips)
    im.save(path); return im


def tmap(data, **kw):
    m = {"type": "map", "orientation": "orthogonal", "width": 3, "height": 2, "tilewidth": 16, "tileheight": 16, "infinite": False,
         "tilesets": [{"firstgid": 1, "name": "t", "image": "t.png", "tilewidth": 16, "tileheight": 16, "columns": 2, "tilecount": 4, "imagewidth": 32, "imageheight": 32}],
         "layers": [{"id": 1, "name": "ground", "type": "tilelayer", "width": 3, "height": 2, "visible": True, "data": data}]}
    m.update(kw); return m


def test_tile_preview(tmp_path):
    tileset_png(tmp_path / "t.png")
    img, n = tile_preview.render(tmap([1, 2, 3, 4, 0, 1]), base_dir=str(tmp_path)); a = np.array(img)
    assert img.size == (48, 32) and n == 5
    assert tuple(a[8, 24]) == (0, 255, 0, 255) and tuple(a[8, 40]) == (0, 0, 255, 255) and tuple(a[24, 8]) == (255, 255, 0, 255) and a[24, 24, 3] == 0 and tuple(a[20, 8 + 32]) == (255, 0, 0, 255)
    # flips: marker pixel of tile 0 at (1,1) moves with H, V and D flags
    H, V, D = tile_preview.H, tile_preview.V, tile_preview.D
    def marker(flag):
        im, _ = tile_preview.render(tmap([1 | flag, 0, 0, 0, 0, 0]), base_dir=str(tmp_path)); a = np.array(im)[:16, :16]
        ys, xs = np.where((a[..., :3] == 255).all(-1)); return int(xs[0]), int(ys[0])
    assert marker(0) == (1, 1) and marker(H) == (14, 1) and marker(V) == (1, 14) and marker(H | V) == (14, 14) and marker(D) == (1, 1) and marker(D | H) == (14, 1) and marker(D | V) == (1, 14)
    # an asymmetric tile (white pixel at x=2, y=5) pins down Tiled's order: diagonal (transpose) first, then H, then V
    asym = Image.new("RGBA", (16, 16), (0, 0, 0, 255)); asym.putpixel((2, 5), (255, 255, 255, 255)); asym.save(tmp_path / "asym.png")
    for flag, want in ((D | H, (10, 2)), (D | V, (5, 13)), (D, (5, 2)), (H, (13, 5))):
        im, _ = tile_preview.render(tmap([1 | flag, 0, 0, 0, 0, 0]), str(tmp_path / "asym.png"), str(tmp_path)); b = np.array(im)[:16, :16]
        ys, xs = np.where((b[..., :3] == 255).all(-1)); assert (int(xs[0]), int(ys[0])) == want, flag
    # layers, hidden, scale, flat fallback, objects, grid
    m = tmap([1, 1, 1, 1, 1, 1]); m["layers"].append({"id": 2, "name": "hid", "type": "tilelayer", "width": 3, "height": 2, "visible": False, "data": [2] * 6})
    assert tuple(np.array(tile_preview.render(m, base_dir=str(tmp_path))[0])[8, 8]) == (255, 0, 0, 255)
    assert tuple(np.array(tile_preview.render(m, base_dir=str(tmp_path), layers={"hid"})[0])[8, 8]) == (0, 255, 0, 255)
    assert tile_preview.render(m, base_dir=str(tmp_path), scale=3)[0].size == (144, 96)
    m2 = tmap([5, 6, 0, 0, 0, 0]); m2["tilesets"][0]["image"] = "missing.png"; im, n = tile_preview.render(m2, base_dir=str(tmp_path)); assert n == 2 and np.array(im)[8, 8, 3] == 255 and not (np.array(im)[8, 8] == np.array(im)[8, 24]).all()
    m3 = tmap([1] * 6); m3["layers"].append({"id": 3, "name": "o", "type": "objectgroup", "visible": True, "objects": [{"id": 1, "name": "spawn", "x": 8, "y": 8, "width": 0, "height": 0, "point": True}, {"id": 2, "x": 0, "y": 0, "width": 10, "height": 10}]})
    plain = np.array(tile_preview.render(m3, base_dir=str(tmp_path))[0]); withobj = np.array(tile_preview.render(m3, base_dir=str(tmp_path), objects=True, grid=True)[0]); assert (plain != withobj).any()
    bare = tmap([1, 2, 3, 0, 0, 5]); bare["tilesets"] = []
    im, n = tile_preview.render(bare, base_dir=str(tmp_path)); assert n == 4 and np.array(im)[8, 8, 3] == 255                                   # no tilesets: flat colours
    im, n = tile_preview.render(bare, str(tmp_path / "t.png"), str(tmp_path)); assert n == 4 and tuple(np.array(im)[8, 24]) == (0, 255, 0, 255)    # --tileset used as tileset 1
    with pytest.raises(SystemExit): tile_preview.render(tmap([1] * 6, orientation="isometric"))
    json.dump(tmap([1, 2, 3, 4, 0, 1]), open(tmp_path / "m.json", "w"))
    assert tile_preview.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "o.png"), "--scale", "2", "--bg", "#102030", "--grid", "--objects"]) == 0 and Image.open(tmp_path / "o.png").size == (96, 64)
    assert tuple(np.array(Image.open(tmp_path / "o.png"))[50, 48][:3]) == (0x10, 0x20, 0x30)                          # --bg fills the empty cell (col 1, row 1)


# ---------- sfx-bank
def _w(path, x, sr=8000, ch=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def test_sfx_bank(tmp_path):
    a = 0.5 * np.sin(np.arange(800) * 0.2); b = 0.3 * np.sin(np.arange(1600) * 0.05); c = 0.4 * np.sin(np.arange(1200) * 0.4)
    _w(tmp_path / "a.wav", a); _w(tmp_path / "b.wav", b); _w(tmp_path / "c.wav", c, sr=16000)
    x, sr, idx = sfx_bank.pack([str(tmp_path / f"{n}.wav") for n in "abc"], gap=0.05)
    assert sr == 16000 and x.shape[1] == 1 and list(idx) == ["a", "b", "c"]
    assert idx["a"]["start"] == 0 and idx["a"]["end"] == 1600 and idx["b"]["start"] == 1600 + 800 and idx["b"]["end"] - idx["b"]["start"] == 3200 and idx["c"]["end"] - idx["c"]["start"] == 1200
    assert abs(x[idx["a"]["end"]:idx["b"]["start"]]).max() == 0                                            # silence between clips
    assert abs(idx["a"]["start_s"] - 0) < 1e-9 and abs(idx["b"]["start_s"] - 0.15) < 1e-9
    h = sfx_bank.howler(idx)["sprite"]; assert h["b"] == [150, 200] and h["a"] == [0, 100]
    assert sfx_bank.main(["pack", str(tmp_path / "a.wav"), str(tmp_path / "b.wav"), str(tmp_path / "c.wav"), "-o", str(tmp_path / "bank"), "--howler", "--mono"]) == 0
    meta = json.load(open(tmp_path / "bank.json")); assert meta["sample_rate"] == 16000 and set(meta["clips"]) == {"a", "b", "c"} and (tmp_path / "bank.howler.json").exists()
    assert sfx_bank.main(["unpack", str(tmp_path / "bank.wav"), str(tmp_path / "bank.json"), "-o", str(tmp_path / "out")]) == 0
    got, gsr = audio_tidy.read_wav(str(tmp_path / "out" / "a.wav")); want, _ = audio_tidy.read_wav(str(tmp_path / "a.wav"))
    assert gsr == 16000 and len(got) == 1600 and abs(np.interp(np.arange(0, 1600, 2), np.arange(1600), got[:, 0])[100:700] - want[100:700, 0]).max() < 0.02          # a is 8 kHz resampled to 16 kHz
    got_b, _ = audio_tidy.read_wav(str(tmp_path / "out" / "b.wav")); assert len(got_b) == 3200
    x2, sr2, _ = sfx_bank.pack([str(tmp_path / "a.wav"), str(tmp_path / "b.wav")], rate=8000); assert sr2 == 8000 and len(x2) == 800 + 400 + 1600 + 400
    _w(tmp_path / "st.wav", np.stack([a, a * 0.5], 1).reshape(-1), ch=2); xs, _, _ = sfx_bank.pack([str(tmp_path / "st.wav"), str(tmp_path / "a.wav")], rate=8000); assert xs.shape[1] == 2
    xm, _, _ = sfx_bank.pack([str(tmp_path / "st.wav"), str(tmp_path / "a.wav")], rate=8000, mono=True); assert xm.shape[1] == 1
    import shutil; os.makedirs(tmp_path / "dup" / "s", exist_ok=True); shutil.copy(tmp_path / "a.wav", tmp_path / "dup" / "s" / "a.wav")
    with pytest.raises(SystemExit): sfx_bank.pack([str(tmp_path / "a.wav"), str(tmp_path / "dup" / "s" / "a.wav")])
    with pytest.raises(SystemExit): sfx_bank.pack([])
    bad = dict(meta["clips"]); bad["a"] = {"start": 0, "end": 10 ** 9}
    with pytest.raises(SystemExit): sfx_bank.unpack(str(tmp_path / "bank.wav"), bad, str(tmp_path / "bad"))


# ---------- asset-rename
def tree(root, names):
    for n in names:
        p = root / n; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("x:" + n)


def test_asset_rename(tmp_path):
    root = tmp_path / "assets"; tree(root, ["Hero Walk 01.PNG", "enemyBoss-idle.png", "ui/Start Button.png", "ui/already_ok.png", "sfx/Door Open!.wav"])
    mv = dict(asset_rename.plan(str(root), "snake", ext_lower=True))
    assert mv == {"Hero Walk 01.PNG": "hero_walk_01.png", "enemyBoss-idle.png": "enemy_boss_idle.png", "ui/Start Button.png": "ui/start_button.png", "sfx/Door Open!.wav": "sfx/door_open.wav"}
    assert dict(asset_rename.plan(str(root), "kebab"))["ui/Start Button.png"] == "ui/start-button.png"
    assert dict(asset_rename.plan(str(root), "keep", replace=[("Hero", "Knight")], prefix="p_", suffix="_v2"))["Hero Walk 01.PNG"] == "p_Knight Walk 01_v2.PNG"
    assert dict(asset_rename.plan(str(root), "keep", regex=[(r"\s+(\d+)$", r"_\1")]))["Hero Walk 01.PNG"] == "Hero Walk_01.PNG"
    assert list(dict(asset_rename.plan(str(root), "snake", include=(".wav",)))) == ["sfx/Door Open!.wav"]
    # dry run changes nothing
    assert asset_rename.main(["run", str(root), "--case", "snake"]) == 0 and (root / "Hero Walk 01.PNG").exists()
    # references are fixed, undo restores
    refs = tmp_path / "game"; refs.mkdir(); (refs / "level.tscn").write_text('path="res://assets/Hero Walk 01.PNG" and "Start Button.png" and "xStart Button.png"\n'); (refs / "keep.json").write_text('{"a":"Hero Walk 01.PNG.bak"}')
    log = tmp_path / "undo.json"
    assert asset_rename.main(["run", str(root), "--case", "snake", "--ext-lower", "--apply", "--log", str(log), "--fix-refs", str(refs)]) == 0
    assert sorted(os.listdir(root)) == ["enemy_boss_idle.png", "hero_walk_01.png", "sfx", "ui"] and (root / "ui" / "start_button.png").read_text() == "x:ui/Start Button.png" and (root / "ui" / "already_ok.png").exists()
    t = (refs / "level.tscn").read_text(); assert "hero_walk_01.png" in t and "start_button.png" in t and "xStart Button.png" in t              # whole-name matches only
    assert "Hero Walk 01.PNG.bak" in (refs / "keep.json").read_text()                                                                       # not a whole name: left alone
    assert asset_rename.main(["undo", str(log)]) == 0 and (root / "Hero Walk 01.PNG").read_text() == "x:Hero Walk 01.PNG" and (root / "sfx" / "Door Open!.wav").exists() and not (root / "ui" / "start_button.png").exists()


def test_asset_rename_safety(tmp_path):
    root = tmp_path / "a"; tree(root, ["My File.png", "my_file.png", "Other.png", "x/Same Name.png", "x/same_name.PNG"])
    assert any("my_file.png" in e for e in asset_rename.check(str(root), asset_rename.plan(str(root), "snake")))                              # target exists
    root2 = tmp_path / "b"; tree(root2, ["A B.png", "A-B.png"])
    errs = asset_rename.check(str(root2), asset_rename.plan(str(root2), "snake")); assert errs and "would all become" in errs[0]
    assert asset_rename.main(["run", str(root2), "--case", "snake", "--apply"]) == 1 and sorted(os.listdir(root2)) == ["A B.png", "A-B.png"]    # nothing touched on a conflict
    root3 = tmp_path / "c"; tree(root3, ["Hero.png"])
    assert asset_rename.main(["run", str(root3), "--case", "lower", "--apply", "--log", str(tmp_path / "l.json")]) == 0 and os.listdir(root3) == ["hero.png"]        # case-only rename
    root4 = tmp_path / "d"; tree(root4, ["a.png", "b.png"]); assert asset_rename.check(str(root4), [("a.png", "b.png"), ("b.png", "a.png")]) == []; asset_rename.apply(str(root4), [("a.png", "b.png"), ("b.png", "a.png")])
    assert (root4 / "a.png").read_text() == "x:b.png" and (root4 / "b.png").read_text() == "x:a.png"                                           # a swap works
    with pytest.raises(SystemExit): asset_rename.plan(str(root4), "snake", regex=[(".*", "")])
    assert asset_rename.convert("myFile Name-2", "snake") == "my_file_name_2" and asset_rename.convert("My File", "kebab") == "my-file" and asset_rename.convert("My_File", "lower") == "my_file"


# ---------- lit-preview
def test_lit_preview(tmp_path):
    spr = Image.new("RGBA", (8, 8), (200, 100, 50, 255)); spr.putpixel((0, 0), (0, 0, 0, 0))
    flat = Image.new("RGB", (8, 8), (128, 128, 255))
    top = np.array(lit_preview.shade(spr, flat, [([0, 0, 1.0], (255, 255, 255))], 0.2, directional=True))
    assert top[4, 4, 0] == 240 and top[0, 0, 3] == 0                                       # head-on light on a flat normal: brighter than albedo, alpha kept
    side = np.array(lit_preview.shade(spr, flat, [([1.0, 0, 0.0], (255, 255, 255))], 0.2, directional=True)); assert abs(int(side[4, 4, 0]) - 200 * 0.2) <= 2     # grazing light: ambient only
    nm = np.zeros((8, 8, 3), np.uint8); nm[..., :] = (255, 128, 128)                                                                           # normal pointing right (+x)
    lit_r = np.array(lit_preview.shade(spr, Image.fromarray(nm), [([1.0, 0, 0.2], (255, 255, 255))], 0.1, directional=True)); lit_l = np.array(lit_preview.shade(spr, Image.fromarray(nm), [([-1.0, 0, 0.2], (255, 255, 255))], 0.1, directional=True))
    assert lit_r[4, 4, 0] > lit_l[4, 4, 0] + 50                                                                                                # facing the light is brighter than facing away
    up = Image.fromarray(np.tile(np.array([128, 255, 128], np.uint8), (8, 8, 1)))                                                              # green up = OpenGL +y = toward image top
    li = lambda y, fg=False: int(np.array(lit_preview.shade(spr, up, [([0, y, 0.2], (255, 255, 255))], 0.0, directional=True, flip_green=fg))[4, 4, 0])
    assert li(-1) > li(1) and li(1, True) > li(-1, True)                                                                                      # light above (negative image y) lights an up-facing normal; DirectX flips it
    pt = np.array(lit_preview.shade(spr, flat, [([0, 0, 20.0], (255, 255, 255))], 0.0)); assert pt[1, 1, 0] > pt[7, 7, 0] > 150          # a point light at the top-left falls off with angle toward the far corner
    sp = lambda s: int(np.array(lit_preview.shade(spr, flat, [([0, 0, 1.0], (255, 255, 255))], 0.2, spec=s, shininess=8, directional=True))[4, 4, 2]); assert sp(0.8) > sp(0.0)
    col = np.array(lit_preview.shade(spr, flat, [([0, 0, 1.0], (255, 0, 0))], 0.0, directional=True)); assert col[4, 4, 1] == 0 and col[4, 4, 0] > 0                       # coloured light
    spr.save(tmp_path / "s.png"); flat.save(tmp_path / "n.png")
    assert lit_preview.main([str(tmp_path / "s.png"), str(tmp_path / "n.png"), "-o", str(tmp_path / "o.png"), "--light", "2,2,6,#ffeecc", "--spec", "0.3"]) == 0
    assert lit_preview.main([str(tmp_path / "s.png"), str(tmp_path / "n.png"), "-o", str(tmp_path / "o.gif"), "--orbit", "6", "--bg", "#222222"]) == 0
    g = Image.open(tmp_path / "o.gif"); assert g.n_frames == 6


# ---------- drop-sim
T = {"goblin": {"rolls": 2, "entries": [{"item": "gold", "weight": 50, "min": 1, "max": 5}, {"item": "sword", "weight": 1}, {"nothing": True, "weight": 39}, {"table": "gems", "weight": 10}], "guaranteed": [{"item": "bone", "count": 2}]},
     "gems": {"entries": [{"item": "ruby", "weight": 1}, {"item": "opal", "weight": 3}]},
     "boss": {"entries": [{"item": "crown", "weight": 1}, {"nothing": True, "weight": 99}], "pity": {"item": "crown", "after": 20}},
     "ranged": {"rolls": [1, 3], "entries": [{"item": "x", "weight": 1}, {"nothing": True, "weight": 3}]}}


def test_drop_sim_exact_and_sim():
    p, q = drop_sim.exact(T, "goblin")
    per = 0.5; assert abs(p["gold"] - (1 - (1 - per) ** 2)) < 1e-12 and abs(q["gold"] - 2 * 0.5 * 3) < 1e-12                                       # two rolls, p=0.5, mean qty 3
    assert abs(p["sword"] - (1 - 0.99 ** 2)) < 1e-12 and p["bone"] == 1.0 and q["bone"] == 2.0
    assert abs(p["ruby"] - (1 - (1 - 0.1 * 0.25) ** 2)) < 1e-12 and abs(p["opal"] - (1 - (1 - 0.1 * 0.75) ** 2)) < 1e-12                          # nested table probability
    pr, _ = drop_sim.exact(T, "ranged"); assert abs(pr["x"] - sum(1 - 0.75 ** r for r in (1, 2, 3)) / 3) < 1e-12
    res = drop_sim.analyse(T, "goblin", trials=40000, seed=3)
    for i in ("gold", "sword", "ruby", "opal", "bone"): assert res[i]["ci95"][0] - 0.003 <= res[i]["p_exact"] <= res[i]["ci95"][1] + 0.003, i
    assert abs(res["gold"]["qty_sim"] - res["gold"]["qty_exact"]) < 0.1 and res["bone"]["p_sim"] == 1.0
    assert drop_sim.analyse(T, "goblin", trials=2000, seed=5) == drop_sim.analyse(T, "goblin", trials=2000, seed=5)                              # deterministic
    assert res["sword"]["kills_for_50"] == 35 and res["sword"]["kills_for_90"] == 115                                                            # ceil(ln(.5)/ln(1-0.0199))
    assert drop_sim.kills_for(0.5, 0.9) == 4 and drop_sim.kills_for(1.0, 0.5) == 1 and drop_sim.kills_for(0, 0.5) is None


def test_drop_sim_pity_and_validation(tmp_path):
    res = drop_sim.analyse(T, "boss", trials=20000, seed=1)
    assert res["crown"]["p_exact"] == 0.01 and res["crown"]["longest_dry_streak"] <= 20 and res["crown"]["p_sim"] > 0.04                          # pity caps the dry streak and raises the real rate
    nopity = {"boss": {"entries": T["boss"]["entries"]}}; assert drop_sim.analyse(nopity, "boss", trials=20000, seed=1)["crown"]["longest_dry_streak"] > 150
    with pytest.raises(SystemExit): drop_sim.validate({"a": {"entries": [{"table": "b", "weight": 1}]}, "b": {"entries": [{"table": "a", "weight": 1}]}})
    with pytest.raises(SystemExit): drop_sim.validate({"a": {"entries": [{"table": "zzz", "weight": 1}]}})
    with pytest.raises(SystemExit): drop_sim.validate({"a": {"entries": [{"item": "x", "weight": 0}]}})
    with pytest.raises(SystemExit): drop_sim.validate({"a": {"entries": [{"item": "x", "weight": -1}, {"item": "y", "weight": 3}]}})
    with pytest.raises(SystemExit): drop_sim.validate({"a": {"entries": []}})
    json.dump({"tables": T}, open(tmp_path / "t.json", "w"))
    assert drop_sim.main([str(tmp_path / "t.json"), "--trials", "2000", "--json", str(tmp_path / "r.json"), "--expect", "goblin:sword:0.015:0.025", "--expect", "boss:crown:0.01:0.01"]) == 0
    assert drop_sim.main([str(tmp_path / "t.json"), "--table", "boss", "--trials", "500", "--expect", "boss:crown:0.05:0.1"]) == 1 and list(json.load(open(tmp_path / "r.json"))) == ["goblin", "gems", "boss", "ranged"]
    assert drop_sim.main([str(tmp_path / "t.json"), "--table", "boss", "--trials", "500", "--expect", "boss:nothing_here:0:0"]) == 0


# ---------- level-curve
def test_level_curve():
    r = level_curve.build("linear", 5, base=100, step=50); assert [x["value"] for x in r] == [100, 150, 200, 250, 300] and r[-1]["cumulative"] == 1000 and r[0]["ratio"] is None and r[1]["ratio"] == 1.5
    assert [x["value"] for x in level_curve.build("poly", 4, power=2, base=10)] == [10, 40, 90, 160]
    e = level_curve.build("exp", 4, base=100, growth=2); assert [x["value"] for x in e] == [100, 200, 400, 800] and all(x["ratio"] == 2.0 for x in e[1:])
    c = level_curve.build("custom", 10, anchors=[(1, 100), (10, 100000)]); assert c[0]["value"] == 100 and c[-1]["value"] == 100000 and abs(c[4]["ratio"] - 10 ** (3 / 9)) < 0.01                    # geometric between anchors
    t = level_curve.build("exp", 20, target_total=1_000_000, base=1, growth=1.3); assert abs(t[-1]["cumulative"] - 1_000_000) < 20
    n = level_curve.build("exp", 6, use_nice=True, base=137, growth=1.37); assert all(len(str(int(x["value"])).rstrip("0")) <= 2 for x in n)
    h = level_curve.build("linear", 4, per_hour=100, base=100, step=100); assert h[-1]["hours_cumulative"] == 10.0 and h[0]["hours"] == 1.0
    assert level_curve.warnings(level_curve.build("exp", 10, base=10, growth=1.2)) == []
    bumpy = level_curve.build("custom", 12, anchors=[(1, 100), (6, 200), (7, 5000), (12, 10000)]); w = level_curve.warnings(bumpy, spike=1.5); assert any("level 7" in x for x in w)
    falling = [{"level": 1, "value": 100, "ratio": None}, {"level": 2, "value": 50, "ratio": 0.5}]; assert "falls" in level_curve.warnings(falling)[0]
    assert "exceeds" in level_curve.warnings(h, max_hours=5)[0]
    with pytest.raises(SystemExit): level_curve.raw("custom", 10, anchors=[(1, 100)])
    with pytest.raises(SystemExit): level_curve.raw("custom", 10, anchors=[(1, 100), (5, 200)])
    with pytest.raises(SystemExit): level_curve.raw("custom", 10, anchors=[(1, 0), (10, 5)])
    assert "<polyline" in level_curve.svg(r) and "(log)" in level_curve.svg(r, log=True)


def test_level_curve_cli(tmp_path):
    assert level_curve.main(["--kind", "exp", "--levels", "10", "--growth", "1.2", "--csv", str(tmp_path / "c.csv"), "--json", str(tmp_path / "c.json"), "--svg", str(tmp_path / "c.svg"), "--per-hour", "500"]) == 0
    assert open(tmp_path / "c.csv").readline().strip() == "level,value,cumulative,ratio,hours,hours_cumulative" and len(json.load(open(tmp_path / "c.json"))["rows"]) == 10
    assert level_curve.main(["--kind", "custom", "--levels", "12", "--anchors", "1:100,6:200,7:5000,12:10000", "--strict"]) == 1


# ---------- font-subset
def real_font():
    for g in ("/usr/share/fonts/**/DejaVuSans.ttf", "/usr/share/fonts/**/*.ttf"):
        f = glob.glob(g, recursive=True)
        if f: return f[0]


@pytest.mark.skipif(font_subset.subset is None or real_font() is None, reason="needs fontTools and a system TTF")
def test_font_subset(tmp_path):
    f = real_font(); txt = tmp_path / "t.txt"; txt.write_text("Hello, world! \u00e9\n")
    out = tmp_path / "sub.ttf"; r = font_subset.do_subset(f, font_subset.used_chars([str(txt)]), str(out))
    assert r["after"] < r["before"] * 0.2 and r["missing"] == []
    cm = font_subset.TTFont(str(out)).getBestCmap(); assert set(map(chr, cm)) >= set("Helo, wrd!\u00e9 ") and ord("Z") not in cm and ord("q") not in cm
    r2 = font_subset.do_subset(f, {"A", "\ue000"}, str(tmp_path / "m.ttf")); assert r2["missing"] == ["\ue000"] and r2["kept"] == 1
    r3 = font_subset.do_subset(f, set("abc"), str(tmp_path / "w.woff"), flavor="woff"); assert open(tmp_path / "w.woff", "rb").read(4) == b"wOFF"
    r4 = font_subset.do_subset(f, set("abc"), str(tmp_path / "nh.ttf"), drop_hinting=True); assert r4["after"] <= font_subset.do_subset(f, set("abc"), str(tmp_path / "h.ttf"))["after"]
    assert font_subset.main([f, str(txt), "-o", str(tmp_path / "cli.ttf"), "--ascii"]) == 0 and font_subset.TTFont(str(tmp_path / "cli.ttf")).getBestCmap().get(ord("~"))
    with pytest.raises(SystemExit): font_subset.main([f])


# ---------- colorblind-sim
def test_colorblind_sim(tmp_path):
    for k in colorblind_sim.TYPES:
        g = colorblind_sim.simulate_rgb(np.array([[128.0, 128, 128], [255, 255, 255], [0, 0, 0]]), k); assert np.abs(g - np.array([[128, 128, 128], [255, 255, 255], [0, 0, 0]])).max() < 1.0, k       # greys stay grey
    for k in colorblind_sim.M: assert np.allclose(colorblind_sim.M[k].sum(1), 1.0, atol=1e-5)
    red = np.array([255.0, 0, 0]); p = colorblind_sim.simulate_rgb(red, "protan"); d = colorblind_sim.simulate_rgb(red, "deutan")
    assert p[0] < 150 and p[1] > 60 and d[0] < 230 and p[0] < d[0]                                                                       # protanopes see red much darker than deuteranopes do
    assert np.allclose(colorblind_sim.simulate_rgb(red, "protan", 0.0), red, atol=1e-6) and abs(colorblind_sim.simulate_rgb(red, "protan", 0.5)[0] - red[0]) > 5
    ac = colorblind_sim.simulate_rgb(np.array([200.0, 50, 50]), "achroma"); assert abs(ac[0] - ac[1]) < 1e-6 and abs(ac[1] - ac[2]) < 1e-6
    assert colorblind_sim.delta_e(np.array([0.0, 0, 0]), np.array([255.0, 255, 255])) > 99 and colorblind_sim.delta_e(red, red) == 0
    rep = colorblind_sim.palette_report(["#e03030", "#30b030", "#3060e0"], min_delta=10); rg = next(r for r in rep if r["pair"] == ("#e03030", "#30b030"))
    assert rg["normal"] > 60 and rg["deutan"] < rg["normal"] / 2
    safe = colorblind_sim.palette_report(["#000000", "#ffffff", "#ffd000"], min_delta=10); assert not any(r["flag"] for r in safe)
    close = colorblind_sim.palette_report(["#808080", "#828282"], min_delta=10); assert close[0]["flag"]
    img = Image.new("RGBA", (4, 4), (255, 0, 0, 128)); img.save(tmp_path / "i.png")
    out = colorblind_sim.simulate(img, "deutan"); assert np.array(out)[0, 0, 3] == 128
    assert colorblind_sim.main(["sim", str(tmp_path / "i.png"), "-o", str(tmp_path / "o")]) == 0 and sorted(os.listdir(tmp_path / "o")) == ["i_achroma.png", "i_deutan.png", "i_protan.png", "i_tritan.png"]
    assert colorblind_sim.main(["sim", str(tmp_path / "i.png"), "-o", str(tmp_path / "o2"), "--type", "tritan"]) == 0 and os.listdir(tmp_path / "o2") == ["i_tritan.png"]
    assert colorblind_sim.main(["palette", "#000000,#ffffff,#ffd000"]) == 0 and colorblind_sim.main(["palette", "#808080,#828282"]) == 1
