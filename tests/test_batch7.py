import csv, json, os, zipfile
import numpy as np
import pytest
from PIL import Image
import normal_fix, anim_meta, terrain_erode, tex_gen, curve_gen, loc_convert, patch_pack, icon_gen
import asset_manifest, terrain_noise, atlas_pack


# ---------- normal-fix
def test_normal_fix(tmp_path):
    rng = np.random.default_rng(0)
    v = rng.normal(size=(32, 32, 3)); v[..., 2] = np.abs(v[..., 2]) + 0.5; v /= np.linalg.norm(v, axis=-1, keepdims=True)
    good = normal_fix.encode(v)
    s = normal_fix.stats(good); assert s["mean_length_error"] < 0.01 and s["pct_into_surface"] == 0
    bad = normal_fix.encode(v * 0.5 + np.array([0, 0, 0.1]) )                     # shrunk vectors: not unit length
    assert normal_fix.stats(bad)["mean_length_error"] > 0.2
    fixed = normal_fix.fix(bad); assert normal_fix.stats(fixed)["mean_length_error"] < 0.02
    fg, _ = normal_fix.decode(normal_fix.fix(good, flip_green=True)); og, _ = normal_fix.decode(good)
    assert np.abs(fg[..., 1] + og[..., 1]).max() < 0.03 and np.abs(fg[..., 0] - og[..., 0]).max() < 0.03
    # rebuild z from a two-channel map
    rg = np.array(good); rg[..., 2] = 0; rb, _ = normal_fix.decode(normal_fix.fix(Image.fromarray(rg, "RGBA"), rebuild_z=True))
    assert np.abs(rb[..., 2] - og[..., 2]).max() < 0.05
    # strength 0 gives a flat map; into-surface vectors are clamped
    flat, _ = normal_fix.decode(normal_fix.fix(good, strength=0.0)); assert flat[..., 2].min() > 0.99
    down = normal_fix.encode(np.array([[[0, 0.6, -0.8]]])); assert normal_fix.decode(normal_fix.fix(down))[0][0, 0, 2] >= 0
    blank = Image.new("RGBA", (2, 2), (128, 128, 128, 255)); assert normal_fix.decode(normal_fix.fix(blank))[0][0, 0, 2] > 0.99   # mid-grey (empty) texels become flat
    a = normal_fix.encode(v, np.full((32, 32), 40)); assert np.array(normal_fix.fix(a))[0, 0, 3] == 40 and np.array(normal_fix.fix(a, alpha="opaque"))[0, 0, 3] == 255
    bad.save(tmp_path / "n.png")
    assert normal_fix.main(["check", str(tmp_path / "n.png"), "--max-error", "0.05"]) == 1
    normal_fix.main(["fix", str(tmp_path / "n.png"), "-o", str(tmp_path / "o")]); assert normal_fix.main(["check", str(tmp_path / "o" / "n.png"), "--max-error", "0.05"]) == 0


# ---------- anim-meta
def test_anim_meta(tmp_path):
    names = ["walk_01", "walk_02", "walk_03", "walk_10", "idle-1", "idle-2", "attack_1", "attack_2", "attack_4", "icon", "tree", "coin_1"]
    clips, singles, warn = anim_meta.build(names, 12, {"idle": 4}, {"attack"})
    assert clips["walk"]["frames"] == ["walk_01", "walk_02", "walk_03", "walk_10"] and clips["idle"]["fps"] == 4.0 and clips["idle"]["duration"] == 0.5
    assert clips["attack"]["loop"] is False and clips["walk"]["loop"] is True
    assert any("attack" in w and "gaps" in w for w in warn) and "coin_1" in singles and "icon" in singles and "coin" not in clips
    assert [x for x in anim_meta.build(["a_9", "a_10", "a_2"], 10)[0]["a"]["frames"]] == ["a_2", "a_9", "a_10"]            # numeric, not alphabetical
    assert any("unknown clip" in w for w in anim_meta.build(names, 12, {"nope": 3})[2])
    ph = anim_meta.phaser(clips, "hero"); a = [x for x in ph["anims"] if x["key"] == "attack"][0]
    assert a["repeat"] == 0 and a["frames"][0] == {"key": "hero", "frame": "attack_1"} and [x for x in ph["anims"] if x["key"] == "walk"][0]["repeat"] == -1
    fr = tmp_path / "f"; fr.mkdir()
    for n in ("run_1", "run_2", "x"): Image.new("RGBA", (4, 4)).save(fr / f"{n}.png")
    anim_meta.main([str(fr), "--clips", str(tmp_path / "c.json"), "--phaser", str(tmp_path / "p.json"), "--fps", "run=8"])
    assert json.load(open(tmp_path / "c.json"))["clips"]["run"]["fps"] == 8.0
    json.dump({"frames": [{"filename": "z_1"}, {"filename": "z_2"}]}, open(tmp_path / "a.json", "w")); assert anim_meta.names_from(str(tmp_path / "a.json")) == ["z_1", "z_2"]


# ---------- terrain-erode
def test_terrain_erode(tmp_path):
    h = terrain_noise.fbm(64, seed=2, tile=True)
    t = terrain_erode.thermal(h, 40, talus=0.005, wrap=True)
    assert abs(t.sum() - h.sum()) < 1e-6 and np.abs(np.diff(t, axis=1)).max() < np.abs(np.diff(h, axis=1)).max()            # mass kept, slopes reduced
    t2 = terrain_erode.thermal(h, 40, talus=0.005, wrap=False); assert abs(t2.sum() - h.sum()) < 1e-6
    spike = np.zeros((9, 9)); spike[4, 4] = 1.0; ts = terrain_erode.thermal(spike, 30, talus=0.01); assert ts[4, 4] < 0.5 and ts[4, 3] > 0
    hy, flow = terrain_erode.hydraulic(h, 40, wrap=True)
    assert abs(hy.sum() - h.sum()) < 1e-6 and not np.allclose(hy, h) and flow.max() == 1.0 and hy.min() >= -1e-9
    hy2, _ = terrain_erode.hydraulic(h, 40, wrap=True); assert np.array_equal(hy, hy2)                                       # deterministic
    hn, _ = terrain_erode.hydraulic(h, 20, wrap=False); assert abs(hn.sum() - h.sum()) < 1e-6
    ramp = np.tile(np.linspace(0, 1, 32), (32, 1)); rh, rf = terrain_erode.hydraulic(ramp, 30); assert abs(rh.sum() - ramp.sum()) < 1e-6
    terrain_erode.save16(h, str(tmp_path / "h.png")); assert np.abs(terrain_erode.load(str(tmp_path / "h.png")) - h).max() < 2e-5
    terrain_erode.main([str(tmp_path / "h.png"), "-o", str(tmp_path / "e.png"), "--flow", str(tmp_path / "f.png"), "--hydraulic", "20", "--thermal", "10", "--wrap"])
    assert Image.open(tmp_path / "e.png").mode == "I;16" and Image.open(tmp_path / "f.png").size == (64, 64)


# ---------- tex-gen
@pytest.mark.parametrize("pattern", tex_gen.PATTERNS)
def test_tex_gen_tiles(pattern):
    img, h = tex_gen.generate(pattern, 64, seed=3)
    a = np.array(img).astype(float)
    # the wrap-around step must look like one of the interior steps: no bigger than the biggest column/row step inside the image
    col_seam = np.abs(a[:, 0] - a[:, -1]).mean(); row_seam = np.abs(a[0] - a[-1]).mean()
    col_max = np.abs(np.diff(a, axis=1)).mean(axis=(0, 2)).max(); row_max = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2)).max()
    assert col_seam <= col_max * 1.1 + 2 and row_seam <= row_max * 1.1 + 2, (pattern, col_seam, col_max, row_seam, row_max)
    assert img.size == (64, 64) and h.shape == (64, 64) and 0 <= h.min() and h.max() <= 1
    img2, _ = tex_gen.generate(pattern, 64, seed=3); assert np.array_equal(np.array(img), np.array(img2))
    if pattern != "checker":                                                      # checker is colour-only, the seed only affects grain
        assert not np.array_equal(np.array(img), np.array(tex_gen.generate(pattern, 64, seed=4)[0]))


def test_tex_gen_details(tmp_path):
    img, h = tex_gen.generate("bricks", 128, seed=1, rows=8, cols=4)
    assert h.min() == 0 and h.max() > 0.9                                         # mortar lines are recessed
    mortar = np.array(img)[h == 0].mean(0); body = np.array(img)[h > 0.9].mean(0); assert abs(mortar - body).sum() > 30
    c, _ = tex_gen.generate("checker", 64, 0, a="#ff0000", b="#0000ff", n=2); assert np.array(c)[5, 5, 0] > np.array(c)[5, 5, 2] and np.array(c)[5, 40, 2] > np.array(c)[5, 40, 0]
    n = np.array(tex_gen.normal_from_height(h)).astype(float) / 255 * 2 - 1; assert np.abs(np.linalg.norm(n, axis=-1) - 1).max() < 0.03
    tex_gen.main(["cells", "-o", str(tmp_path / "t.png"), "--size", "64", "--height", "--normal", "--count", "6"])
    assert all((tmp_path / f).exists() for f in ("t.png", "t_height.png", "t_normal.png"))


# ---------- curve-gen
def test_curve_gen(tmp_path):
    P = np.array([[0, 0], [4, 3], [8, 0], [12, 3]], float)
    c = curve_gen.build(P, "catmull", per=20)
    assert np.allclose(c[0], P[0]) and np.allclose(c[-1], P[-1]) and any(np.allclose(c[i], P[1]) for i in range(len(c)))           # passes through every control point
    assert any(np.allclose(c[i], P[2]) for i in range(len(c)))
    cl = curve_gen.build(P, "catmull", closed=True, per=20); assert np.allclose(cl[0], cl[-1]) and len(cl) == 4 * 20 + 1
    b = curve_gen.build(np.array([[0, 0], [0, 10], [10, 10], [10, 0]], float), "bezier", per=50)
    assert np.allclose(b[0], [0, 0]) and np.allclose(b[-1], [10, 0]) and np.allclose(b[len(b) // 2], [5, 7.5], atol=0.2)           # cubic Bezier midpoint
    r = curve_gen.build(P, "catmull", per=40, spacing=0.5); d = np.linalg.norm(np.diff(r, axis=0), axis=1)
    assert np.allclose(d[:-1], 0.5, atol=0.03) and np.allclose(r[-1], P[-1])
    assert len(curve_gen.build(P, "linear", count=17)) == 17
    lin = curve_gen.build(np.array([[0, 0, 0], [3, 4, 0]], float), "linear", spacing=1.0); assert abs(curve_gen.arclen(lin)[-1] - 5) < 1e-9 and lin.shape[1] == 3
    rows = curve_gen.annotate(lin); assert rows[0]["u"] == 0 and rows[-1]["u"] == 1 and abs(np.linalg.norm(rows[1]["tangent"]) - 1) < 1e-3
    curve_gen.main(["--points", "0,0;4,3;8,0", "--spacing", "1", "--json", str(tmp_path / "c.json"), "--csv", str(tmp_path / "c.csv"), "--svg", str(tmp_path / "c.svg")])
    assert json.load(open(tmp_path / "c.json"))["samples"][0]["p"] == [0, 0] and "<path" in open(tmp_path / "c.svg").read() and open(tmp_path / "c.csv").readline().strip() == "i,x,y,s,u"
    json.dump([[0, 0], [1, 1]], open(tmp_path / "p.json", "w")); assert curve_gen.load_points(str(tmp_path / "p.json")).shape == (2, 2)
    with pytest.raises(SystemExit): curve_gen.build(np.array([[0.0, 0.0]]))


# ---------- loc-convert
ROWS = [{"id": "ui.start", "en": "Start", "fr": "D\u00e9marrer", "ja": "\u30b9\u30bf\u30fc\u30c8"},
        {"id": "dlg.1", "en": 'He said "hi"\nand left.\n', "fr": 'Il a dit "salut"\net il est parti.\n', "ja": ""},
        {"id": "path", "en": "C:\\temp\\x\tend", "fr": "C:\\temp\\x\tfin", "ja": "x"}]


def test_loc_convert_po_roundtrip(tmp_path):
    for l in ("fr", "ja"): loc_convert.write_po(ROWS, "en", l, str(tmp_path / f"{l}.po"))
    loc_convert.write_po(ROWS, "en", None, str(tmp_path / "template.pot"))
    txt = open(tmp_path / "fr.po", encoding="utf-8").read(); assert 'msgctxt "ui.start"' in txt and 'msgstr "D\u00e9marrer"' in txt and '"Language: fr\\n"' in txt
    rows, langs = loc_convert.from_po({"fr": str(tmp_path / "fr.po"), "ja": str(tmp_path / "ja.po")}, None, "en")
    assert langs == ["fr", "ja"] and {r["id"]: r for r in rows} == {r["id"]: r for r in ROWS}
    assert all(e["msgstr"] == "" for e in loc_convert.parse_po(open(tmp_path / "template.pot", encoding="utf-8").read()))
    assert len(loc_convert.parse_po(txt)) == 3                                  # the header is not a string
    # gettext tools expect the multi-line form for newlines
    assert 'msgid ""\n"He said \\"hi\\"\\n"\n"and left.\\n"' in txt


def test_loc_convert_formats(tmp_path):
    f = tmp_path / "s.csv"
    with open(f, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "en", "fr", "ja"]); w.writeheader(); w.writerows(ROWS)
    for cmd in ("to-po", "to-json", "to-xliff"): assert loc_convert.main([cmd, str(f), "-o", str(tmp_path / cmd)]) == 0
    assert sorted(os.listdir(tmp_path / "to-po")) == ["fr.po", "ja.po", "template.pot"]
    assert loc_convert.main(["to-json", str(f), "-o", str(tmp_path / "nest"), "--nested"]) == 0
    assert json.load(open(tmp_path / "nest" / "fr.json"))["ui"]["start"] == "D\u00e9marrer" and json.load(open(tmp_path / "to-json" / "fr.json"))["ui.start"] == "D\u00e9marrer"
    x = open(tmp_path / "to-xliff" / "ja.xlf", encoding="utf-8").read(); assert 'target-language="ja"' in x and 'state="new"' in x                      # empty ja for dlg.1
    import xml.etree.ElementTree as ET; ET.fromstring(x.encode())
    assert "&quot;" in open(tmp_path / "to-xliff" / "fr.xlf", encoding="utf-8").read()
    out = tmp_path / "back.csv"; loc_convert.main(["from-po", str(tmp_path / "to-po" / "fr.po"), str(tmp_path / "to-po" / "ja.po"), "-o", str(out)])
    assert {r["id"]: r for r in csv.DictReader(open(out, encoding="utf-8"))}["dlg.1"]["fr"] == ROWS[1]["fr"]
    with pytest.raises(SystemExit): loc_convert.to_json([{"id": "a", "en": "x"}, {"id": "a.b", "en": "y"}], "en", True)


# ---------- patch-pack
def _tree(root, files):
    for k, v in files.items():
        p = root / k; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(v)


def test_patch_pack(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _tree(old, {"a.txt": b"a" * 100, "b.txt": b"b" * 100, "c/gone.bin": b"gone", "c/same.bin": b"s" * 50, "move_me.dat": b"m" * 200})
    _tree(new, {"a.txt": b"a" * 100, "b.txt": b"B" * 120, "c/same.bin": b"s" * 50, "new/n.bin": b"n" * 10, "moved/move_me.dat": b"m" * 200})
    man = asset_manifest.build(str(old)); z = tmp_path / "p.zip"
    patch, size = patch_pack.make(man, str(new), str(z))
    assert patch["ops"]["add"] == ["new/n.bin"] and patch["ops"]["change"] == ["b.txt"] and patch["ops"]["remove"] == ["c/gone.bin"] and patch["ops"]["rename"] == [["move_me.dat", "moved/move_me.dat"]]
    names = zipfile.ZipFile(z).namelist(); assert "files/b.txt" in names and "files/moved/move_me.dat" not in names and "files/a.txt" not in names     # renames cost nothing
    r = patch_pack.apply(str(z), str(old), dry_run=True); assert r["ok"] and r["written"] == 0 and not (old / "new").exists()
    out = tmp_path / "out"; r = patch_pack.apply(str(z), str(old), str(out)); assert r["ok"] and r["errors"] == [] and r["written"] == 4
    assert asset_manifest.verify(asset_manifest.build(str(new)), str(out)) == {"missing": [], "modified": [], "extra": []} and (old / "c" / "gone.bin").exists()   # old untouched
    assert patch_pack.apply(str(z), str(out))["ok"] is False                                                    # already patched: base hashes do not match
    (old / "b.txt").write_bytes(b"tampered"); r = patch_pack.apply(str(z), str(old)); assert not r["ok"] and r["errors"][0][0] == "b.txt" and (old / "b.txt").read_bytes() == b"tampered"
    assert patch_pack.main(["info", str(z)]) == 0 and patch_pack.main(["apply", str(z), str(old), "--dry-run"]) == 1
    # in-place apply on an untouched copy
    import shutil; shutil.rmtree(old); _tree(old, {"a.txt": b"a" * 100, "b.txt": b"b" * 100, "c/gone.bin": b"gone", "c/same.bin": b"s" * 50, "move_me.dat": b"m" * 200})
    assert patch_pack.main(["apply", str(z), str(old)]) == 0 and (old / "moved" / "move_me.dat").exists() and not (old / "c" / "gone.bin").exists()


def test_patch_pack_rejects_traversal(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as f: f.writestr("patch.json", json.dumps({"ops": {"add": ["../evil.txt"], "change": [], "remove": [], "rename": []}, "base": {}, "result": {"../evil.txt": "0"}})); f.writestr("files/../evil.txt", "x")
    (tmp_path / "t").mkdir()
    with pytest.raises(SystemExit): patch_pack.apply(str(z), str(tmp_path / "t"))
    assert not (tmp_path / "evil.txt").exists()


# ---------- icon-gen
def test_icon_gen(tmp_path):
    m = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    m.paste(Image.new("RGBA", (600, 600), (220, 30, 30, 255)), (212, 212))
    made, warned = icon_gen.generate(m, str(tmp_path / "i"), bg="#102030", pad=10); assert not warned
    ico = Image.open(tmp_path / "i" / "windows" / "icon.ico"); assert {(16, 16), (32, 32), (256, 256)} <= ico.info["sizes"]
    assert Image.open(tmp_path / "i" / "macos" / "icon.icns").size[0] >= 512
    assert Image.open(tmp_path / "i" / "android" / "mipmap-xxxhdpi" / "ic_launcher.png").size == (192, 192) and Image.open(tmp_path / "i" / "android" / "mipmap-mdpi" / "ic_launcher.png").size == (48, 48)
    io = Image.open(tmp_path / "i" / "ios" / "Icon-1024.png"); assert io.mode == "RGB" and io.getpixel((2, 2)) == (0x10, 0x20, 0x30) and io.getpixel((512, 512)) == (220, 30, 30)    # flattened, no alpha
    mk = Image.open(tmp_path / "i" / "web" / "icon-maskable-512.png"); assert mk.getpixel((2, 2)) == (0x10, 0x20, 0x30, 255) and mk.getpixel((256, 256))[:3] == (220, 30, 30)
    fg = Image.open(tmp_path / "i" / "android" / "adaptive-foreground-432.png"); assert fg.size == (432, 432) and fg.getpixel((2, 2))[3] == 0
    assert Image.open(tmp_path / "i" / "web" / "icon-512.png").getpixel((2, 2))[3] == 0                         # web icons keep transparency
    assert len(made) == len(set(made)) >= 30
    wide = Image.new("RGBA", (200, 100), (255, 0, 0, 255)); wide.save(tmp_path / "w.png")
    assert icon_gen.main([str(tmp_path / "w.png"), "-o", str(tmp_path / "w")]) == 0 and Image.open(tmp_path / "w" / "web" / "icon-192.png").size == (192, 192)
