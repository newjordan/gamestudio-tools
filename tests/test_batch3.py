import csv, json, os, struct
import numpy as np
import pytest
from PIL import Image, ImageFont
import tilemap_convert, obj_to_glb, channel_pack, bmfont_gen, vo_diff, frames_to_sheet, palette_extract, asset_manifest
import gltf_inspect, dungeon_gen, dialogue_extract


# ---------- tilemap-convert
def test_tilemap_roundtrips(tmp_path):
    dungeon_gen.main(["--seed", "3", "--size", "20x12", "-o", str(tmp_path / "d")])
    m = json.load(open(tmp_path / "d.json"))
    tilemap_convert.main(["to-csv", str(tmp_path / "d.json"), "-o", str(tmp_path / "c")])
    rows = list(csv.reader(open(tmp_path / "c_dungeon.csv")))
    assert len(rows) == 12 and len(rows[0]) == 20
    tilemap_convert.main(["from-csv", str(tmp_path / "c_dungeon.csv"), "-o", str(tmp_path / "back.json"), "--tile", "16x16"])
    assert json.load(open(tmp_path / "back.json"))["layers"][0]["data"] == m["layers"][0]["data"]
    tilemap_convert.main(["to-ascii", str(tmp_path / "d.json"), "--legend", "1:.,2:#", "-o", str(tmp_path / "a.txt")])
    assert (tmp_path / "a.txt").read_text() == (tmp_path / "d.txt").read_text()
    tilemap_convert.main(["from-ascii", str(tmp_path / "a.txt"), "-o", str(tmp_path / "b2.json"), "--legend", ".:1,#:2"])
    assert json.load(open(tmp_path / "b2.json"))["layers"][0]["data"] == m["layers"][0]["data"]


def test_tilemap_flip_flags_masked_and_reported(tmp_path, capsys):
    m = tilemap_convert.make_map([[[1, 2], [3, 4]]], 16, 16)
    m["layers"][0]["data"][1] = 2 | 0x80000000
    p = tmp_path / "m.json"; json.dump(m, open(p, "w"))
    tilemap_convert.main(["to-csv", str(p), "-o", str(tmp_path / "x")])
    assert [r for r in csv.reader(open(tmp_path / "x_layer1.csv"))] == [["1", "2"], ["3", "4"]]
    assert "1 flipped" in capsys.readouterr().err
    assert tilemap_convert.stats(m)["layer1"]["flipped"] == 1


# ---------- obj-to-glb
CUBE = """mtllib cube.mtl
v -1 -1 -1
v 1 -1 -1
v 1 1 -1
v -1 1 -1
v -1 -1 1
v 1 -1 1
v 1 1 1
v -1 1 1
vt 0 0
vt 1 0
vt 1 1
vt 0 1
usemtl red
f 1/1 2/2 3/3 4/4
f 5/1 6/2 7/3 8/4
usemtl tex
f 1/1 2/2 6/3 5/4
f 4/1 3/2 7/3 8/4
f -4/1 -3/2 -2/3 -1/4
"""


def test_obj_to_glb(tmp_path):
    (tmp_path / "cube.obj").write_text(CUBE)
    (tmp_path / "cube.mtl").write_text("newmtl red\nKd 1 0 0\nnewmtl tex\nKd 1 1 1\nmap_Kd t.png\n")
    Image.new("RGB", (8, 8), (10, 20, 30)).save(tmp_path / "t.png")
    obj_to_glb.main([str(tmp_path / "cube.obj"), "-o", str(tmp_path / "out"), "--scale", "2"])
    r = gltf_inspect.inspect(str(tmp_path / "out" / "cube.glb"))
    assert r["totals"]["triangles"] == 10          # 5 quads
    assert len(r["meshes"][0]["primitives"]) == 2 and len(r["materials"]) == 2
    assert r["textures"][0]["size"] == (8, 8)
    assert r["bounds"]["size"] == [4, 4, 4]        # scale 2 on a 2-unit cube
    assert not r["warnings"], r["warnings"]        # normals + uvs generated
    g, b = obj_to_glb.convert(str(tmp_path / "cube.obj"))
    assert g["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"] == [1.0, 0.0, 0.0, 1.0]
    # flat normals: first quad lies on z=-1 plane -> normals are +/-z, unit length
    import glb_lod
    glb_lod.save_glb(str(tmp_path / "t.glb"), g, b); gg, bb = glb_lod.load_glb(str(tmp_path / "t.glb"))
    n = glb_lod.read_acc(gg, bb, gg["meshes"][0]["primitives"][0]["attributes"]["NORMAL"])
    assert np.allclose(np.linalg.norm(n, axis=1), 1, atol=1e-4) and np.allclose(np.abs(n[:, 2]), 1)
    uv = glb_lod.read_acc(gg, bb, gg["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"])
    assert uv.min() >= 0 and uv.max() <= 1


# ---------- channel-pack
def test_channel_pack_roundtrip(tmp_path):
    ao = np.full((8, 8), 200, np.uint8); ro = np.full((4, 4), 100, np.uint8); me = np.full((8, 8), 7, np.uint8)
    for n, a in (("ao", ao), ("ro", ro), ("me", me)): Image.fromarray(a).save(tmp_path / f"{n}.png")
    channel_pack.main(["pack", "--preset", "orm", "--ao", str(tmp_path / "ao.png"), "--roughness", str(tmp_path / "ro.png"),
                       "--metallic", str(tmp_path / "me.png"), "-o", str(tmp_path / "orm.png")])
    o = np.array(Image.open(tmp_path / "orm.png"))
    assert o.shape == (8, 8, 4) and (o[..., 0] == 200).all() and (o[..., 1] == 100).all() and (o[..., 2] == 7).all() and (o[..., 3] == 255).all()
    channel_pack.main(["unpack", str(tmp_path / "orm.png"), "--preset", "orm", "-o", str(tmp_path / "u")])
    assert np.array(Image.open(tmp_path / "u" / "orm_ao.png"))[0, 0] == 200
    assert np.array(Image.open(tmp_path / "u" / "orm_metallic.png"))[0, 0] == 7
    # missing channels use preset fills; unity mask puts smoothness in alpha, invert flips
    channel_pack.main(["pack", "--preset", "unity-mask", "--metallic", str(tmp_path / "me.png"), "-o", str(tmp_path / "mask.png")])
    m = np.array(Image.open(tmp_path / "mask.png"))
    assert m[0, 0, 0] == 7 and m[0, 0, 1] == 255 and m[0, 0, 3] == 128
    ch = channel_pack.pack({"r": ao, "g": None}, {"g": 0}, invert="r")
    assert np.array(ch)[0, 0, 0] == 55


# ---------- bmfont-gen
def test_bmfont_gen(tmp_path):
    try:
        ImageFont.load_default(16)
    except Exception:
        pytest.skip("no FreeType default font")
    bmfont_gen.main(["--font", "default", "--size", "16", "-o", str(tmp_path / "f"), "--chars", "ABCabc123 ,.!"])
    fnt = (tmp_path / "f.fnt").read_text().splitlines()
    atlas = np.array(Image.open(tmp_path / "f.png"))
    assert fnt[0].startswith("info face=") and fnt[1].startswith("common lineHeight=")
    chars = [dict(kv.split("=") for kv in l.split()[1:]) for l in fnt if l.startswith("char ")]
    assert len(chars) == len(set("ABCabc123 ,.!")) and fnt[3] == f"chars count={len(chars)}"
    boxes = []
    for c in chars:
        x, y, w, h = (int(c[k]) for k in ("x", "y", "width", "height"))
        assert x + w <= atlas.shape[1] and y + h <= atlas.shape[0]
        if c["id"] == str(ord("A")):
            assert w > 4 and atlas[y:y + h, x:x + w, 3].max() > 200
        if w and h:
            boxes.append((x, y, x + w, y + h))
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
    space = next(c for c in chars if c["id"] == "32")
    assert int(space["xadvance"]) > 0 and space["width"] == "0"
    bmfont_gen.main(["--font", "default", "--size", "12", "--no-aa", "-o", str(tmp_path / "p"), "--chars", "Hi"])
    px = np.array(Image.open(tmp_path / "p.png"))[..., 3]
    assert set(np.unique(px)) <= {0, 255}


# ---------- vo-diff
def test_vo_diff(tmp_path):
    (tmp_path / "v1.yarn").write_text("title: A\n---\nAva: Welcome to the station. #line:l1\nBen: Where are the others? #line:l2\nAva: Stay close to me. #line:l3\nBen: I will. #line:l4\n===\n")
    (tmp_path / "v2.yarn").write_text("title: A\n---\nAva: Welcome to the station. #line:l1\nBen: Where are the others gone? #line:l2\nBen: Stay close to me. #line:l3\nAva: A brand new line about the reactor. #line:l5\n===\n")
    dialogue_extract.main([str(tmp_path / "v1.yarn"), "-o", str(tmp_path / "v1.csv")])
    dialogue_extract.main([str(tmp_path / "v2.yarn"), "-o", str(tmp_path / "v2.csv")])
    d = vo_diff.diff(vo_diff.load(tmp_path / "v1.csv"), vo_diff.load(tmp_path / "v2.csv"))
    assert [r["id"] for r in d["added"]] == ["l5"] and [r["id"] for r in d["removed"]] == ["l4"]
    assert [r["id"] for r in d["minor"] + d["changed"]] == ["l2"]
    assert [r["id"] for r in d["speaker_changed"]] == ["l3"] and d["unchanged"] == 1
    aud = tmp_path / "rec"; aud.mkdir(); (aud / "l1.wav").write_bytes(b"x"); (aud / "l2.ogg").write_bytes(b"x")
    vo_diff.main([str(tmp_path / "v1.csv"), str(tmp_path / "v2.csv"), "-o", str(tmp_path / "todo.csv"), "--audio-dir", str(aud), "--json", str(tmp_path / "d.json")])
    todo = {r["id"]: r["reason"] for r in csv.DictReader(open(tmp_path / "todo.csv"))}
    assert set(todo) == {"l5", "l2", "l3"} and todo["l5"] == "new" and todo["l3"] == "speaker changed"
    mins = json.load(open(tmp_path / "d.json"))["rerecord_minutes"]
    assert set(mins) == {"Ava", "Ben"} and all(v > 0 for v in mins.values())


# ---------- frames-to-sheet
def test_frames_to_sheet(tmp_path):
    frames = []
    for i in range(6):
        im = Image.new("RGBA", (20, 20), (0, 0, 0, 0)); im.paste((40 * i + 10, 100, 200, 255), (5 + i, 6, 10 + i, 14)); frames.append(im)
    # GIF with per-frame durations
    pal = [f.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE) for f in frames]
    pal[0].save(tmp_path / "a.gif", save_all=True, append_images=pal[1:], duration=[50, 50, 100, 100, 50, 50], loop=0)
    fr, du = frames_to_sheet.read_frames(str(tmp_path / "a.gif"))
    assert len(fr) == 6 and du == [50, 50, 100, 100, 50, 50]
    # folder input, uniform crop keeps alignment
    d = tmp_path / "fr"; d.mkdir()
    for i, f in enumerate(frames): f.save(d / f"f{i}.png")
    frames_to_sheet.main([str(d), "-o", str(tmp_path / "s"), "--columns", "3", "--scale", "2"])
    meta = json.load(open(tmp_path / "s.json"))
    assert meta["count"] == 6 and meta["columns"] == 3 and meta["rows"] == 2
    assert (meta["frame_width"], meta["frame_height"]) == (20, 16)   # union bbox x 5..15, y 6..14, scaled x2
    sheet = Image.open(tmp_path / "s.png")
    assert sheet.size == (meta["frame_width"] * 3, meta["frame_height"] * 2)
    f0 = meta["frames"][0]
    assert sheet.getpixel((f0["x"] + 1, f0["y"] + 1))[3] == 255            # frame 0 sprite starts at the crop corner
    f5 = meta["frames"][5]
    assert sheet.getpixel((f5["x"] + 18, f5["y"] + 1))[3] == 255 and sheet.getpixel((f5["x"] + 1, f5["y"] + 1))[3] == 0   # sprite drifted right by 5px
    frames_to_sheet.main([str(d), "-o", str(tmp_path / "t"), "--max-frames", "3"])
    assert json.load(open(tmp_path / "t.json"))["count"] == 3
    keyed = frames_to_sheet.key_out(Image.new("RGBA", (2, 2), (0, 255, 0, 255)), (0, 255, 0))
    assert keyed.getpixel((0, 0))[3] == 0


# ---------- palette-extract
def test_palette_extract(tmp_path):
    im = Image.new("RGBA", (6, 2), (0, 0, 0, 0))
    for x, c in enumerate([(255, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0), (255, 255, 255)]):
        im.putpixel((x, 0), c + (255,))
    im.putpixel((0, 1), (9, 9, 9, 0))      # transparent: ignored
    p = tmp_path / "i.png"; im.save(p)
    palette_extract.main([str(p), "-o", str(tmp_path / "pal"), "--sort", "luminance"])
    hexes = open(tmp_path / "pal.hex").read().split()
    assert hexes[0] == "000000" and hexes[-1] == "ffffff" and set(hexes) == {"000000", "ff0000", "00ff00", "0000ff", "ffffff"}
    assert "GIMP Palette" in open(tmp_path / "pal.gpl").read()
    assert Image.open(tmp_path / "pal_swatch.png").size == (5 * 16, 16)
    big = Image.fromarray(np.random.default_rng(0).integers(0, 256, (32, 32, 3), np.uint8)); big.save(tmp_path / "n.png")
    palette_extract.main([str(tmp_path / "n.png"), "-o", str(tmp_path / "q"), "-n", "8"])
    assert len(open(tmp_path / "q.hex").read().split()) <= 8
    # round-trips into pixelize's palette loader
    import pixelize
    assert len(pixelize.load_palette(str(tmp_path / "pal.hex"))) == 5 and len(pixelize.load_palette(str(tmp_path / "pal.gpl"))) == 5


# ---------- asset-manifest
def test_asset_manifest(tmp_path):
    a = tmp_path / "a"; (a / "sub").mkdir(parents=True)
    Image.new("RGBA", (4, 4), (1, 2, 3, 255)).save(a / "t.png"); (a / "sub" / "x.txt").write_text("hello"); (a / "junk.tmp").write_text("z")
    (a / "old.bin").write_bytes(b"123456")
    asset_manifest.main(["build", str(a), "-o", str(tmp_path / "m1.json")])
    m1 = json.load(open(tmp_path / "m1.json"))
    assert set(m1["files"]) == {"t.png", "sub/x.txt", "old.bin"} and m1["files"]["t.png"]["w"] == 4
    asset_manifest.main(["build", str(a), "-o", str(tmp_path / "m1b.json")])
    assert open(tmp_path / "m1.json").read() == open(tmp_path / "m1b.json").read()    # deterministic
    assert asset_manifest.main(["verify", str(tmp_path / "m1.json"), str(a)]) == 0
    (a / "sub" / "x.txt").write_text("hello world")                                    # changed
    (a / "new.txt").write_text("fresh")                                                # added
    os.rename(a / "old.bin", a / "renamed.bin")                                        # renamed
    (a / "t.png").unlink()                                                             # removed
    assert asset_manifest.main(["verify", str(tmp_path / "m1.json"), str(a)]) == 1
    asset_manifest.main(["build", str(a), "-o", str(tmp_path / "m2.json")])
    d = asset_manifest.diff(m1, json.load(open(tmp_path / "m2.json")))
    assert d["added"] == ["new.txt"] and d["removed"] == ["t.png"] and d["changed"] == ["sub/x.txt"] and d["renamed"] == [("old.bin", "renamed.bin")]
    assert d["patch_bytes"] == len("hello world") + len("fresh")
    assert asset_manifest.main(["diff", str(tmp_path / "m1.json"), str(tmp_path / "m2.json"), "--fail"]) == 1
    assert asset_manifest.main(["diff", str(tmp_path / "m1.json"), str(tmp_path / "m1.json"), "--fail"]) == 0
