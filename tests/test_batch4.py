import csv, json, os, shutil, subprocess, wave
import numpy as np
import pytest
from PIL import Image
import autotile_gen, pixel_lint, tile_colliders, subtitle_timing, pseudoloc, audio_convert, mesh_colliders, uv_check, build_report
import glb_lod, dungeon_gen, sfx_gen


# ---------- autotile-gen
COL = {(c, r): (40 * c + 10, 60 * r + 20, 100 + 10 * (c + 3 * r), 255) for c in range(3) for r in range(3)}


def _template(t=8):
    im = Image.new("RGBA", (3 * t, 3 * t))
    for (c, r), col in COL.items(): im.paste(col, (c * t, r * t, c * t + t, r * t + t))
    return im


def test_autotile_masks():
    sheet, meta = autotile_gen.build(_template(), 8)
    assert sheet.size == (32, 32) and len(meta["tiles"]) == 16
    px = lambda mask, x, y: sheet.getpixel(((mask % 4) * 8 + x, (mask // 4) * 8 + y))
    assert (px(0, 1, 1), px(0, 6, 1), px(0, 1, 6), px(0, 6, 6)) == (COL[0, 0], COL[2, 0], COL[0, 2], COL[2, 2])   # isolated tile: 4 corners
    assert all(px(15, x, y) == COL[1, 1] for x in (0, 3, 7) for y in (0, 4, 7))                                   # surrounded: fill
    # N,E,S present, W missing -> left edge column on the west side, fill on the east
    m = autotile_gen.N | autotile_gen.E | autotile_gen.S
    assert px(m, 1, 1) == COL[0, 1] and px(m, 1, 6) == COL[0, 1] and px(m, 6, 3) == COL[1, 1]
    # only E present: top-left corner art, right half is top edge
    assert px(autotile_gen.E, 1, 1) == COL[0, 0] and px(autotile_gen.E, 6, 1) == COL[1, 0]
    assert autotile_gen.mask_for([[1, 1, 0], [1, 1, 1], [0, 1, 0]], 1, 1) == 15
    assert autotile_gen.mask_for([[1, 1, 0], [1, 1, 1], [0, 1, 0]], 0, 0) == autotile_gen.E | autotile_gen.S
    with pytest.raises(SystemExit): autotile_gen.build(Image.new("RGBA", (10, 10)), 8)


# ---------- pixel-lint
def test_pixel_lint(tmp_path):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    im.paste((255, 0, 0, 255), (2, 2, 8, 8)); im.paste((0, 255, 0, 255), (8, 8, 12, 12))
    im.putpixel((14, 1), (255, 0, 0, 255))                    # orphan
    im.putpixel((3, 3), (254, 1, 1, 255))                     # near-dup of red
    im.putpixel((9, 9), (0, 0, 255, 128))                     # semi + off-palette
    p = tmp_path / "s.png"; im.save(p)
    (tmp_path / "pal.hex").write_text("ff0000\n00ff00\n")
    msgs = " | ".join(m for _, m in pixel_lint.lint(str(p), 3, pixel_lint.read_palette(str(tmp_path / "pal.hex")), 4))
    for needle in ("colours > 3", "off-palette", "semi-transparent", "orphan pixel(s), first at x=14 y=1", "near-duplicate"): assert needle in msgs, needle
    clean = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); clean.paste((255, 0, 0, 255), (1, 1, 5, 5)); clean.putpixel((5, 5), (0, 255, 0, 255))
    c = tmp_path / "c.png"; clean.save(c)
    assert pixel_lint.lint(str(c), 4) == []
    up = clean.resize((32, 32), Image.Resampling.NEAREST); u = tmp_path / "u.png"; up.save(u)
    assert any("upscaled 4x" in m for _, m in pixel_lint.lint(str(u)))
    assert pixel_lint.main([str(c), "--max-colors", "4"]) == 0 and pixel_lint.main([str(p), "--max-colors", "3"]) == 1


# ---------- tile-colliders
def test_tile_colliders(tmp_path):
    grid = ["#####", "#...#", "#.#.#", "#...#", "#####"]
    m = {"width": 5, "height": 5, "tilewidth": 16, "tileheight": 16, "layers": [{"name": "w", "type": "tilelayer", "width": 5, "height": 5, "data": [1 if c == "#" else 0 for r in grid for c in r]}]}
    p = tmp_path / "m.json"; json.dump(m, open(p, "w"))
    g = tile_colliders.solid_grid(m, None)
    rects = tile_colliders.merge(g)
    covered = np.zeros((5, 5), int)
    for x, y, w, h in rects: covered[y:y + h, x:x + w] += 1
    assert covered.max() == 1 and np.array_equal(covered.astype(bool), np.array(g))      # exact cover, no overlap
    assert len(rects) == 5 and sum(g[y][x] for y in range(5) for x in range(5)) == 17     # 17 tiles into 5 rects (ring sides + pillar)
    big = dungeon_gen.bsp(64, 40, 5)[0]; mm = tile_colliders.merge([[c == 1 for c in row] for row in big])
    assert 0 < len(mm) < sum(c == 1 for row in big for c in row) / 3
    tile_colliders.main([str(p), "-o", str(tmp_path / "o.json"), "--tiled-objects"])
    o = json.load(open(tmp_path / "o.json")); assert o["type"] == "objectgroup" and o["objects"][0]["width"] % 16 == 0
    tile_colliders.main([str(p), "--solid", "2", "-o", str(tmp_path / "e.json")])
    assert json.load(open(tmp_path / "e.json"))["rects"] == []


# ---------- subtitle-timing
def test_subtitle_timing(tmp_path):
    aud = tmp_path / "a"; aud.mkdir()
    sfx_gen.write_wav(str(aud / "l1.wav"), np.zeros(int(44100 * 2.0), np.float32))
    (tmp_path / "l.csv").write_text('id,speaker,text,est_seconds\nl1,Ava,Welcome to the station.,\nl2,Ben,"This is a rather long line of dialogue that should wrap onto a second line nicely.",1.0\nl3,,Hi.,\n')
    subtitle_timing.main([str(tmp_path / "l.csv"), "-o", str(tmp_path / "s"), "--audio-dir", str(aud)])
    j = json.load(open(tmp_path / "s.json")); c = j["cues"]
    assert c[0]["start"] == 0 and abs(c[0]["end"] - 2.15) < 0.01 and c[0]["duration_source"] == "audio"
    assert abs(c[1]["start"] - (c[0]["end"] + 0.3)) < 0.01 and len(c[1]["lines"]) == 2 and c[1]["duration_source"] == "estimate"
    assert c[2]["end"] - c[2]["start"] >= 1.0
    assert any("l2" in w and "chars/s" in w for w in j["warnings"])
    srt = (tmp_path / "s.srt").read_text()
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,150\nAva: Welcome to the station.\n")
    vtt = (tmp_path / "s.vtt").read_text()
    assert vtt.startswith("WEBVTT") and "00:00:00.000 --> 00:00:02.150" in vtt and "<v Ava>" in vtt
    assert subtitle_timing.ts(3725.5) == "01:02:05,500"


# ---------- pseudoloc
def test_pseudoloc(tmp_path):
    s = "Hello {name}, you have %d new <b>items</b> and %1$s.\\nBye [color=red]now[/color] $player$"
    out = pseudoloc.pseudo(s)
    for token in ("{name}", "%d", "<b>", "</b>", "%1$s", "\\n", "[color=red]", "[/color]", "$player$"): assert token in out, token
    assert out.startswith("[") and out.endswith("]") and len(out) >= len(s) * 1.3
    assert "Hello" not in out and "Ĥ" in out or "ĥ" in out or "ħ" in out
    (tmp_path / "s.csv").write_text("id,text\na,Start game\nb,Quit\n")
    pseudoloc.main([str(tmp_path / "s.csv"), "-o", str(tmp_path / "o.csv"), "--new-column", "pseudo"])
    rows = list(csv.DictReader(open(tmp_path / "o.csv")))
    assert rows[0]["text"] == "Start game" and rows[0]["pseudo"].startswith("[Šţåř")


# ---------- audio-convert
@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_audio_convert(tmp_path):
    t = np.arange(44100) / 44100
    sfx_gen.write_wav(str(tmp_path / "tone.wav"), (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32))
    cmd = audio_convert.command("a.wav", "a.ogg", "sfx", loudnorm=-16)
    assert cmd[0] == "ffmpeg" and "libvorbis" in cmd and "loudnorm=I=-16:TP=-1.5:LRA=11" in cmd and cmd[-1] == "a.ogg"
    for preset, ext, codec in (("music", ".ogg", "vorbis"), ("voice", ".opus", "opus"), ("mp3", ".mp3", "mp3"), ("flac", ".flac", "flac")):
        out = tmp_path / preset
        assert audio_convert.main([str(tmp_path / "tone.wav"), "-o", str(out), "--preset", preset]) == 0
        f = out / ("tone" + ext)
        info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name:format=duration", "-of", "json", str(f)], capture_output=True, text=True)
        j = json.loads(info.stdout)
        assert j["streams"][0]["codec_name"] == codec and abs(float(j["format"]["duration"]) - 1.0) < 0.15
    # the same WAV must encode to the same bytes; a wall-clock vendor string used to change the hash
    assert audio_convert.main([str(tmp_path / "tone.wav"), "-o", str(tmp_path / "sfx_a"), "--preset", "sfx"]) == 0
    assert audio_convert.main([str(tmp_path / "tone.wav"), "-o", str(tmp_path / "sfx_b"), "--preset", "sfx"]) == 0
    assert (tmp_path / "sfx_a" / "tone.ogg").read_bytes() == (tmp_path / "sfx_b" / "tone.ogg").read_bytes()
    assert audio_convert.main([str(tmp_path / "tone.wav"), "-o", str(tmp_path / "d"), "--dry-run"]) == 0 and not (tmp_path / "d" / "tone.ogg").exists()


# ---------- glb helpers
def mesh_glb(path, pos, uv=None, idx=None, nodes=None, tex=None):
    import io
    pos = np.asarray(pos, np.float32); idx = np.asarray(idx if idx is not None else np.arange(len(pos)), np.uint16)
    parts, views, off = [], [], 0
    def add(data, tgt=None):
        nonlocal off
        pad = -off % 4; parts.append(b"\0" * pad); off += pad
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if tgt: v["target"] = tgt
        views.append(v); parts.append(data); off += len(data); return len(views) - 1
    accs = [{"bufferView": add(pos.tobytes(), 34962), "componentType": 5126, "count": len(pos), "type": "VEC3", "min": pos.min(0).tolist(), "max": pos.max(0).tolist()}]
    attrs = {"POSITION": 0}
    if uv is not None:
        accs.append({"bufferView": add(np.asarray(uv, np.float32).tobytes(), 34962), "componentType": 5126, "count": len(pos), "type": "VEC2"}); attrs["TEXCOORD_0"] = 1
    accs.append({"bufferView": add(idx.tobytes(), 34963), "componentType": 5123, "count": len(idx), "type": "SCALAR"})
    g = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes or [{"mesh": 0}],
         "meshes": [{"primitives": [{"attributes": attrs, "indices": len(accs) - 1}]}], "accessors": accs, "bufferViews": views}
    if tex:
        b = io.BytesIO(); Image.new("RGB", tex, (1, 1, 1)).save(b, "PNG"); g["images"] = [{"bufferView": add(b.getvalue()), "mimeType": "image/png"}]
    glb_lod.save_glb(str(path), g, b"".join(parts))


def grid(n=10, size=1.0, uvscale=1.0):
    xs, zs = np.meshgrid(np.linspace(0, size, n), np.linspace(0, size, n))
    pos = np.stack([xs, 0 * xs, zs], -1).reshape(-1, 3); uv = np.stack([xs / size, zs / size], -1).reshape(-1, 2) * uvscale
    idx = []
    for y in range(n - 1):
        for x in range(n - 1):
            a, b, c, d = y * n + x, y * n + x + 1, (y + 1) * n + x, (y + 1) * n + x + 1; idx += [a, c, b, b, c, d]
    return pos, uv, idx


def box_pts(sx, sy, sz):
    return np.array([[x, y, z] for x in (-sx / 2, sx / 2) for y in (-sy / 2, sy / 2) for z in (-sz / 2, sz / 2)], np.float32)


# ---------- mesh-colliders
def test_mesh_colliders(tmp_path):
    ang = np.radians(30); q = [0, float(np.sin(ang / 2)), 0, float(np.cos(ang / 2))]
    mesh_glb(tmp_path / "b.glb", box_pts(4, 1, 1), idx=list(range(8)), nodes=[{"mesh": 0, "translation": [10, 2, 0], "rotation": q, "name": "plank"}])
    g, b = mesh_colliders.load_glb(str(tmp_path / "b.glb"))
    parts = mesh_colliders.world_vertices(g, b); assert parts[0][0] == "plank"
    s = mesh_colliders.shapes(parts[0][1])
    assert np.allclose(s["aabb"]["center"], [10, 2, 0], atol=1e-4)
    assert np.allclose(sorted(s["obb"]["size"]), [1, 1, 4], atol=1e-3)
    assert np.prod(s["aabb"]["size"]) > 1.5 * np.prod(s["obb"]["size"])   # OBB hugs the rotated plank, AABB does not
    assert np.allclose(s["obb"]["center"], [10, 2, 0], atol=1e-3)
    assert 2.0 <= s["sphere"]["radius"] <= 2.0 * 1.2 * (np.linalg.norm([4, 1, 1]) / 4.2) + 0.2
    pts = parts[0][1]; assert (np.linalg.norm(pts - np.array(s["sphere"]["center"]), axis=1) <= s["sphere"]["radius"] + 1e-6).all()
    assert s["godot"]["CapsuleShape3D.height"] >= 2 * s["godot"]["CapsuleShape3D.radius"]
    mesh_colliders.main([str(tmp_path / "b.glb"), "-o", str(tmp_path / "c.json"), "--per-node"])
    assert "plank" in json.load(open(tmp_path / "c.json"))["nodes"]
    mesh_glb(tmp_path / "s.glb", box_pts(2, 2, 2), idx=list(range(8)), nodes=[{"children": [1], "scale": [2, 2, 2]}, {"mesh": 0, "translation": [1, 0, 0]}])
    g, b = mesh_colliders.load_glb(str(tmp_path / "s.glb")); v = mesh_colliders.world_vertices(g, b)[0][1]
    assert np.allclose(v.max(0), [4, 2, 2]) and np.allclose(v.min(0), [0, -2, -2])   # parent scale 2 also scales the child translation


# ---------- uv-check
def test_uv_check(tmp_path):
    pos, uv, idx = grid(12, 2.0)
    mesh_glb(tmp_path / "ok.glb", pos, uv, idx, tex=(256, 256))
    r = uv_check.analyse(str(tmp_path / "ok.glb"))
    assert r["triangles"] == 2 * 11 * 11 and r["overlap"] < 0.01 and r["out_of_range"] == 0 and r["degenerate"] == 0 and r["coverage"] > 0.6
    td = r["texel_density"]; assert td["tex_size"] == [256, 256] and abs(td["median"] - 128) < 2 and td["outside_50pct"] == 0   # 256 px across 2 units
    # same UVs for two separate surfaces -> overlap
    pos2 = np.concatenate([pos, pos + [5, 0, 0]]); uv2 = np.concatenate([uv, uv]); idx2 = idx + [i + len(pos) for i in idx]
    mesh_glb(tmp_path / "ov.glb", pos2, uv2, idx2)
    assert uv_check.analyse(str(tmp_path / "ov.glb"), (256, 256))["overlap"] > 0.9
    # uv beyond 0..1 and uneven density (half the mesh gets 4x the UV scale)
    uv3 = uv.copy(); uv3[: len(uv3) // 2] *= 3.0
    mesh_glb(tmp_path / "oor.glb", pos, uv3, idx)
    r3 = uv_check.analyse(str(tmp_path / "oor.glb"), (256, 256))
    assert r3["out_of_range"] > 0.2 and r3["texel_density"]["outside_50pct"] > 0.3
    mesh_glb(tmp_path / "deg.glb", [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 0], [0.5, 0.5], [1, 1]], [0, 1, 2])
    assert uv_check.analyse(str(tmp_path / "deg.glb"))["degenerate"] == 1
    assert uv_check.main([str(tmp_path / "ok.glb"), "--max-overlap", "0.05"]) == 0 and uv_check.main([str(tmp_path / "ov.glb"), "--tex-size", "64x64", "--max-overlap", "0.05"]) == 1


# ---------- build-report
def test_build_report(tmp_path, capsys):
    root = tmp_path / "assets"; root.mkdir()
    Image.new("RGBA", (64, 64)).save(root / "ok_tex.png"); Image.new("RGB", (60, 50)).save(root / "BadName.png")
    pos, uv, idx = grid(6); mesh_glb(root / "prop.glb", pos, uv, idx, tex=(8, 8))
    out = tmp_path / "r.md"
    code = build_report.main([str(root), "-o", str(out), "--save-manifest", str(tmp_path / "m1.json")])
    md = out.read_text()
    assert code == 1 and "# Asset build report" in md and "**FAIL**" in md and "BadName.png" in md and "`prop.glb` | 50 |" in md and "## Size by type" in md
    (root / "BadName.png").unlink(); Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(root / "ok_tex.png")
    code = build_report.main([str(root), "-o", str(out), "--prev-manifest", str(tmp_path / "m1.json")])
    md = out.read_text()
    assert code == 0 and "**PASS**" in md and "removed 1" in md and "changed 1" in md
