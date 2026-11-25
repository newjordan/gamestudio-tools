import csv, json, os, wave
import numpy as np
import pytest
from PIL import Image
import image_diff, texture_seamless, tile_dedupe, atlas_convert, loc_check, sfx_variants, terrain_mesh, dialogue_graph
import atlas_pack, gltf_inspect, terrain_noise, sfx_gen, tilemap_convert


# ---------- image-diff
def test_image_diff(tmp_path):
    a = Image.new("RGBA", (10, 10), (10, 20, 30, 255)); b = a.copy()
    for x in range(2, 5):
        for y in range(3, 5): b.putpixel((x, y), (200, 20, 30, 255))
    r, m = image_diff.diff(a, b)
    assert r["changed_pixels"] == 6 and r["bbox"] == [2, 3, 5, 5] and r["max_diff"] == 190 and abs(r["changed_pct"] - 6.0) < 1e-6
    assert image_diff.diff(a, b, tol=200)[0]["changed_pixels"] == 0
    t1 = Image.new("RGBA", (4, 4), (1, 2, 3, 0)); t2 = Image.new("RGBA", (4, 4), (9, 9, 9, 0))
    assert image_diff.diff(t1, t2)[0]["changed_pixels"] == 0              # hidden RGB under alpha 0 is ignored
    assert "size_mismatch" in image_diff.diff(a, Image.new("RGBA", (5, 5)))[0]
    (tmp_path / "o").mkdir(); (tmp_path / "n").mkdir()
    a.save(tmp_path / "o" / "same.png"); a.save(tmp_path / "n" / "same.png"); a.save(tmp_path / "o" / "chg.png"); b.save(tmp_path / "n" / "chg.png"); a.save(tmp_path / "n" / "new.png")
    code = image_diff.main([str(tmp_path / "o"), str(tmp_path / "n"), "-o", str(tmp_path / "h"), "--json", str(tmp_path / "r.json"), "--max-changed", "10"])
    rep = json.load(open(tmp_path / "r.json"))
    assert rep["same.png"]["status"] == "same" and rep["chg.png"]["status"] == "changed" and rep["new.png"]["status"] == "added" and code == 1
    h = Image.open(tmp_path / "h" / "chg_diff.png"); assert h.getpixel((3, 3)) == (255, 0, 0, 255) and h.getpixel((0, 0)) != (255, 0, 0, 255)
    assert image_diff.main([str(tmp_path / "o" / "same.png"), str(tmp_path / "n" / "same.png"), "--max-changed", "0"]) == 0


# ---------- texture-seamless
def test_texture_seamless(tmp_path):
    rng = np.random.default_rng(1)
    base = terrain_noise.fbm(128, seed=3, tile=False)                  # smooth noise that does NOT wrap
    img = np.stack([base, np.roll(base, 20, 1), base ** 2], -1)
    src = Image.fromarray((img * 255).astype(np.uint8)).convert("RGBA")
    before = texture_seamless.seam_score(np.array(src)[..., :3])
    out = texture_seamless.make_seamless(src)
    after = texture_seamless.seam_score(np.array(out)[..., :3])
    assert before > 3 and after < 1.6 and after < before / 2
    assert out.size == src.size and (np.array(out)[..., 3] == 255).all()
    p = tmp_path / "t.png"; src.save(p)
    texture_seamless.main([str(p), "-o", str(tmp_path / "s.png"), "--preview", str(tmp_path / "pv.png")])
    assert Image.open(tmp_path / "pv.png").size == (256, 256) and Image.open(tmp_path / "s.png").size == (128, 128)
    flat = Image.new("RGBA", (16, 16), (50, 60, 70, 255))
    assert np.array_equal(np.array(texture_seamless.make_seamless(flat)), np.array(flat))          # solid colour stays solid


# ---------- tile-dedupe
def _rand_tile(seed, t=8):
    r = np.random.default_rng(seed); a = r.integers(0, 255, (t, t, 4), np.uint8); a[..., 3] = 255; return a


def test_tile_dedupe_exact_and_empty(tmp_path):
    A, B = _rand_tile(1), _rand_tile(2); E = np.zeros((8, 8, 4), np.uint8); E2 = E.copy(); E2[..., :3] = 77
    tiles = [A, B, A.copy(), E, B.copy(), E2]
    sheet = Image.new("RGBA", (8 * 6, 8)); [sheet.paste(Image.fromarray(t, "RGBA"), (i * 8, 0)) for i, t in enumerate(tiles)]
    sheet.save(tmp_path / "ts.png")
    tile_dedupe.main([str(tmp_path / "ts.png"), "--tile", "8x8", "-o", str(tmp_path / "o")])
    j = json.load(open(tmp_path / "o.json"))
    assert j["original_count"] == 6 and j["unique_count"] == 2
    assert [(r["new"], r["reason"]) for r in j["remap"]] == [(0, "unique"), (1, "unique"), (0, "duplicate"), (None, "empty"), (1, "duplicate"), (None, "empty")]
    assert Image.open(tmp_path / "o.png").size[0] == 8 * 6   # keeps original column count by default


@pytest.mark.parametrize("xf", list(tile_dedupe.XF))
def test_tile_dedupe_transforms_and_map_flags(tmp_path, xf):
    base = _rand_tile(5); dup = tile_dedupe.XF[xf](base).copy()
    tiles = [base, _rand_tile(9), np.ascontiguousarray(dup)]
    unique, remap = tile_dedupe.dedupe(tiles, transforms=True)
    assert remap[2]["new"] == 0 and remap[2]["reason"] == "duplicate" and (remap[2]["xf"] == "none") == (xf == "none")
    m = {"layers": [{"type": "tilelayer", "name": "l", "data": [3, 1, 2], "width": 3, "height": 1}]}
    new = tile_dedupe.remap_map(m, remap)["layers"][0]["data"]
    gid, flags = new[0] & 0x1FFFFFFF, new[0] & 0xE0000000
    canon = unique[gid - 1]
    # apply Tiled's rule: diagonal flip first, then horizontal, then vertical
    t = canon
    if flags & 0x20000000: t = t.transpose(1, 0, 2)
    if flags & 0x80000000: t = t[:, ::-1]
    if flags & 0x40000000: t = t[::-1]
    assert np.array_equal(t, tiles[2]), (xf, hex(flags))


# ---------- atlas-convert
def _atlas(tmp_path):
    d = tmp_path / "spr"; d.mkdir()
    for i, (w, h) in enumerate(((10, 12), (14, 6))):
        im = Image.new("RGBA", (20, 20), (0, 0, 0, 0)); im.paste((255, 0, 0, 255), (3, 4, 3 + w, 4 + h)); im.save(d / f"s{i}.png")
    atlas_pack.main([str(d), "-o", str(tmp_path / "at")])
    return json.load(open(tmp_path / "at.json"))


def test_atlas_convert(tmp_path):
    meta = _atlas(tmp_path)
    arr = atlas_convert.to_array(meta); assert isinstance(arr["frames"], list) and {f["filename"] for f in arr["frames"]} == {"s0", "s1"}
    assert atlas_convert.to_hash(arr) == meta
    gdx = atlas_convert.to_libgdx(meta)
    s0 = meta["frames"]["s0"]
    assert gdx.startswith("\nat.png\nsize: ") and "format: RGBA8888" in gdx
    assert f"s0\n  rotate: false\n  xy: {s0['frame']['x']}, {s0['frame']['y']}\n  size: 10, 12\n  orig: 20, 20\n  offset: 3, {20 - 12 - 4}\n  index: -1" in gdx
    st = atlas_convert.to_starling(meta)
    assert '<TextureAtlas imagePath="at.png">' in st and 'name="s0"' in st and 'frameX="-3" frameY="-4" frameWidth="20" frameHeight="20"' in st
    import xml.dom.minidom; xml.dom.minidom.parseString(st)
    css = atlas_convert.to_css(meta); assert f"background-position: -{s0['frame']['x']}px -{s0['frame']['y']}px" in css and ".spr-s1 {" in css
    atlas_convert.main([str(tmp_path / "at.json"), "--to", "libgdx", "-o", str(tmp_path / "at.atlas"), "--image", "sprites.png"])
    assert (tmp_path / "at.atlas").read_text().split("\n")[1] == "sprites.png"


# ---------- loc-check
def test_loc_check(tmp_path):
    rows = [{"id": "a", "en": "Hello {name}, you have %d <b>gold</b>.", "fr": "Bonjour {name}, vous avez %d <b>or</b>.", "de": "Hallo {nam}, du hast %d Gold.", "ja": "こんにちは{name}、%d <b>ゴールド</b>"},
            {"id": "b", "en": "Start game now please", "fr": "", "de": "Start game now please", "ja": "ゲーム開始"},
            {"id": "c", "en": "Save", "fr": "Sauvegarder la partie en cours maintenant", "de": "Speichern", "ja": "保存"},
            {"id": "a", "en": "dup", "fr": "dup", "de": "dup", "ja": "dup"},
            {"id": "d", "en": "Line1\\nLine2", "fr": "L1 L2", "de": "Z1\\nZ2", "ja": "1\\n2"}]
    res = loc_check.check(rows, "en", ["fr", "de", "ja"])
    has = lambda lvl, i, lang, text: any(r["level"] == lvl and r["id"] == i and r["lang"] == lang and text in r["msg"] for r in res)
    assert has("error", "a", "", "duplicate id") and has("error", "a", "de", "placeholder mismatch") and has("error", "a", "de", "tag mismatch")
    assert not any(r["id"] == "a" and r["lang"] in ("fr", "ja") and r["level"] == "error" for r in res)      # correct placeholders/tags pass
    assert has("error", "b", "fr", "missing") and has("warn", "b", "de", "identical to source")
    assert has("warn", "c", "fr", "length")
    assert has("error", "d", "fr", "escape mismatch") and not any(r["id"] == "d" and r["lang"] == "de" for r in res)
    p = tmp_path / "l.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "en", "fr", "de", "ja"]); w.writeheader(); w.writerows(rows)
    assert loc_check.main([str(p)]) == 1
    clean = [{"id": "x", "en": "Hi {n}", "fr": "Salut {n}"}]
    p2 = tmp_path / "c.csv"
    with open(p2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "en", "fr"]); w.writeheader(); w.writerows(clean)
    assert loc_check.main([str(p2)]) == 0


def test_loc_check_length_rules():
    rows = [{"id": "c", "en": "Save game", "fr": "Sauvegarder la partie en cours", "ja": "保存"},
            {"id": "e", "en": "Save game", "fr": "Sauvegarder", "ja": "ゲームを保存するにはここをクリックしてください"}]
    res = loc_check.check(rows, "en", ["fr", "ja"])
    msgs = {(r["id"], r["lang"]): r["msg"] for r in res if "length" in r["msg"]}
    assert ("c", "fr") in msgs and ("e", "ja") in msgs and ("e", "fr") not in msgs and ("c", "ja") not in msgs


# ---------- sfx-variants
def test_sfx_variants(tmp_path):
    t = np.arange(22050) / 22050
    src = tmp_path / "hit.wav"; sfx_gen.write_wav(str(src), (0.8 * np.sin(2 * np.pi * 300 * t)).astype(np.float32), 22050)
    sfx_variants.main([str(src), "-o", str(tmp_path / "v"), "-n", "6", "--seed", "10", "--semitones", "2", "--peak", "-3", "--offset-ms", "20"])
    meta = json.load(open(tmp_path / "v" / "hit_variants.json")); assert len(meta) == 6
    durs = {m["seconds"] for m in meta}; assert len(durs) >= 5
    for m in meta:
        x, sr = sfx_variants.read_wav(str(tmp_path / "v" / m["file"]))
        assert sr == 22050 and np.abs(x).max() <= 10 ** (-3 / 20) + 1e-3 and abs(m["semitones"]) <= 2
        expect = 1.0 / 2 ** (m["semitones"] / 12)
        assert expect - 0.01 <= len(x) / sr <= expect + 0.03                                  # duration follows pitch (+ up to 20 ms offset)
        zc = np.where(np.diff(np.signbit(x[2000:12000, 0])))[0]; f = len(zc) / 2 / (10000 / sr)
        assert abs(f - 300 * 2 ** (m["semitones"] / 12)) < 25                                  # measured pitch matches the shift
    sfx_variants.main([str(src), "-o", str(tmp_path / "v2"), "-n", "6", "--seed", "10", "--semitones", "2", "--peak", "-3", "--offset-ms", "20"])
    assert json.load(open(tmp_path / "v2" / "hit_variants.json")) == meta                      # deterministic


# ---------- terrain-mesh
def test_terrain_mesh(tmp_path):
    n = 33
    ramp = np.tile(np.linspace(0, 65535, n), (n, 1)).astype(np.uint16)
    Image.fromarray(ramp).save(tmp_path / "h16.png")
    assert Image.open(tmp_path / "h16.png").mode.startswith("I;16")
    terrain_mesh.main([str(tmp_path / "h16.png"), "-o", str(tmp_path / "t.glb"), "--scale", "64,10,64"])
    r = gltf_inspect.inspect(str(tmp_path / "t.glb"))
    assert r["totals"] == {"vertices": 33 * 33, "triangles": 2 * 32 * 32} and not r["warnings"]
    assert np.allclose(r["bounds"]["size"], [64, 10, 64], atol=1e-3)
    import glb_lod
    g, b = glb_lod.load_glb(str(tmp_path / "t.glb")); pr = g["meshes"][0]["primitives"][0]
    nrm = glb_lod.read_acc(g, b, pr["attributes"]["NORMAL"]); pos = glb_lod.read_acc(g, b, pr["attributes"]["POSITION"])
    assert np.allclose(np.linalg.norm(nrm, axis=1), 1, atol=1e-4) and (nrm[:, 0] < 0).all() and nrm[:, 2].std() < 1e-6          # slope rises along +x -> normals lean -x
    tri = glb_lod.read_acc(g, b, pr["indices"]).reshape(-1, 3); a, bb, c = (pos[tri[:, i]] for i in range(3))
    assert (np.cross(bb - a, c - a)[:, 1] > 0).all()                                                                            # counter-clockwise seen from +Y (front faces up)
    flat = np.full((17, 17), 128, np.uint8); Image.fromarray(flat).save(tmp_path / "f.png")
    terrain_mesh.main([str(tmp_path / "f.png"), "-o", str(tmp_path / "c.glb"), "--chunks", "2", "--step", "2"])
    outs = sorted(f for f in os.listdir(tmp_path) if f.startswith("c_c")); assert outs == ["c_c0_0.glb", "c_c0_1.glb", "c_c1_0.glb", "c_c1_1.glb"]
    bs = [gltf_inspect.inspect(str(tmp_path / f))["bounds"] for f in outs]
    assert abs(bs[0]["max"][0] - bs[1]["min"][0]) < 1e-4 or abs(bs[0]["max"][0] - bs[2]["min"][0]) < 1e-4                         # neighbouring chunks share an edge
    assert np.isclose(max(b["max"][0] for b in bs), 100) and np.isclose(min(b["min"][0] for b in bs), 0)
    pn = terrain_noise.fbm(65, seed=1); Image.fromarray((pn * 255).astype(np.uint8)).save(tmp_path / "n.png")
    terrain_mesh.main([str(tmp_path / "n.png"), "-o", str(tmp_path / "n.glb"), "--step", "4"])
    assert gltf_inspect.inspect(str(tmp_path / "n.glb"))["totals"]["triangles"] == 2 * 16 * 16


# ---------- dialogue-graph
YARN = """title: Start
---
Ava: Hi.
-> Go left
    <<jump Left>>
-> Go right
    <<jump Right>>
===
title: Left
---
Ava: Left.
<<jump Nowhere>>
===
title: Right
---
Ava: Right.
===
title: Secret
---
Ava: Nobody finds me.
<<jump Start>>
===
"""
INK = """Welcome.
-> tavern
== tavern ==
Hello.
* [Leave] -> street
* [Drink] -> drink
= drink
Cheers.
-> END
== street ==
Walking on.
== lost ==
Nobody comes here.
-> END
"""


def test_dialogue_graph(tmp_path):
    n = dialogue_graph.parse_yarn(YARN)
    assert list(n) == ["Start", "Left", "Right", "Secret"] and n["Start"]["edges"] == ["Left", "Right"] and n["Right"]["edges"] == []
    rep = dialogue_graph.analyse(n, kind="yarn")
    assert rep["unreachable"] == ["Secret"] and rep["missing_targets"] == [{"from": "Left", "to": "Nowhere"}] and rep["dead_ends"] == []
    k = dialogue_graph.parse_ink(INK)
    rep2 = dialogue_graph.analyse(k, kind="ink")
    assert "tavern" in k and "tavern.drink" in k and "street" in k
    assert rep2["unreachable"] == ["lost"] and rep2["dead_ends"] == ["street"] and rep2["missing_targets"] == [] and rep2["start"] == "(start)"
    (tmp_path / "a.yarn").write_text(YARN); (tmp_path / "b.ink").write_text(INK)
    assert dialogue_graph.main([str(tmp_path / "a.yarn"), "--dot", str(tmp_path / "g.dot"), "--mermaid", str(tmp_path / "g.mmd"), "--json", str(tmp_path / "g.json")]) == 1
    dot = (tmp_path / "g.dot").read_text(); assert dot.startswith("digraph") and '"Left" -> "Nowhere" [color=red' in dot and "lightcoral" in dot
    mm = (tmp_path / "g.mmd").read_text(); assert mm.startswith("flowchart LR") and "Start --> Left" in mm and "Nowhere_" not in mm.split("Left --> ")[0]
    assert json.load(open(tmp_path / "g.json"))["graph"]["Start"] == ["Left", "Right"]
    assert dialogue_graph.main([str(tmp_path / "b.ink")]) == 0 and dialogue_graph.main([str(tmp_path / "b.ink"), "--strict"]) == 1
