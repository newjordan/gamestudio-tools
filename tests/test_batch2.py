import ast, json, os, struct, subprocess, shutil, wave
import numpy as np
import pytest
from PIL import Image
import tile_extrude, palette_swap, sprite_fx, glb_lod, godot_import_presets, loop_finder, asset_viewer, fleet_jobs
import gltf_inspect, atlas_pack, dungeon_gen


# ---------- tile-extrude
def _tileset():
    im = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    im.paste((255, 0, 0, 255), (0, 0, 16, 16)); im.paste((0, 0, 255, 255), (16, 0, 32, 16))
    return im


def test_extrude_edges_and_params():
    out, meta = tile_extrude.extrude(_tileset(), 16, 16, n=2)
    assert meta == {"tilewidth": 16, "tileheight": 16, "margin": 2, "spacing": 4, "columns": 2, "rows": 1,
                    "imagewidth": 40, "imageheight": 20}
    assert out.size == (40, 20)
    assert out.getpixel((0, 0)) == (255, 0, 0, 255) and out.getpixel((1, 10)) == (255, 0, 0, 255)  # extruded gutter
    assert out.getpixel((2, 2)) == (255, 0, 0, 255) and out.getpixel((17, 5)) == (255, 0, 0, 255)
    assert out.getpixel((20 + 0, 5)) == (0, 0, 255, 255) and out.getpixel((22, 2)) == (0, 0, 255, 255)
    # tile 1 starts at margin + 1*(tw+spacing) = 2+20 = 22 and the red tile ends at x=17 + 2 extruded px
    assert out.getpixel((18, 5)) == (255, 0, 0, 255) and out.getpixel((19, 5)) == (255, 0, 0, 255)


def test_bleed_fills_rgb_not_alpha():
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); im.putpixel((3, 3), (200, 100, 50, 255))
    out = tile_extrude.bleed(im, 2)
    assert out.getpixel((3, 2))[:3] == (200, 100, 50) and out.getpixel((3, 2))[3] == 0
    assert out.getpixel((3, 3)) == (200, 100, 50, 255) and out.getpixel((0, 0))[:3] == (0, 0, 0)


# ---------- palette-swap
def test_palette_swap(tmp_path):
    im = Image.new("RGBA", (4, 1), (255, 0, 0, 255)); im.putpixel((3, 0), (255, 0, 0, 0)); im.putpixel((1, 0), (0, 255, 0, 255))
    src = tmp_path / "s.png"; im.save(src)
    out = palette_swap.swap_colors(im, [((255, 0, 0), (0, 0, 255))])
    assert out.getpixel((0, 0)) == (0, 0, 255, 255) and out.getpixel((1, 0)) == (0, 255, 0, 255) and out.getpixel((3, 0))[3] == 0
    near = Image.new("RGBA", (1, 1), (250, 3, 0, 255))
    assert palette_swap.swap_colors(near, [((255, 0, 0), (1, 2, 3))], 8).getpixel((0, 0)) == (1, 2, 3, 255)
    assert palette_swap.swap_colors(near, [((255, 0, 0), (1, 2, 3))], 0).getpixel((0, 0)) == (250, 3, 0, 255)
    h = palette_swap.hsv_shift(Image.new("RGBA", (1, 1), (255, 0, 0, 255)), hue=120).getpixel((0, 0))
    assert h[1] > 200 and h[0] < 60 and h[3] == 255
    (tmp_path / "v.json").write_text(json.dumps({"blue": {"ff0000": "0000ff"}, "ghost": {"hue": 180}}))
    palette_swap.main([str(src), "-o", str(tmp_path / "o"), "--variants", str(tmp_path / "v.json")])
    assert sorted(os.listdir(tmp_path / "o")) == ["s_blue.png", "s_ghost.png"]
    (tmp_path / "a.hex").write_text("ff0000\n00ff00\n"); (tmp_path / "b.hex").write_text("111111\n222222\n")
    palette_swap.main([str(src), "-o", str(tmp_path / "p"), "--from", str(tmp_path / "a.hex"), "--to", str(tmp_path / "b.hex")])
    o = Image.open(tmp_path / "p" / "s_swap.png").convert("RGBA")
    assert o.getpixel((0, 0)) == (17, 17, 17, 255) and o.getpixel((1, 0)) == (34, 34, 34, 255)


# ---------- sprite-fx
def test_sprite_fx(tmp_path):
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); im.paste((255, 255, 0, 255), (2, 2, 6, 6))
    out = sprite_fx.bake(im, outline=1, outline_color=(255, 0, 0, 255), shadow=(2, 2, 0.5, 0))
    pad = sprite_fx.pad_for(1, (2, 2, 0.5, 0))
    assert out.size == (8 + 2 * pad, 8 + 2 * pad)
    assert out.getpixel((pad + 1, pad + 2)) == (255, 0, 0, 255)       # left outline
    assert out.getpixel((pad + 2, pad + 2)) == (255, 255, 0, 255)     # sprite intact on top
    sh = out.getpixel((pad + 7, pad + 7))                             # shadow only (beyond outline), semi-transparent black
    assert sh[3] in range(100, 140) and sh[:3] == (0, 0, 0)
    f = sprite_fx.flash(out, 1.0)
    assert f.getpixel((pad + 2, pad + 2)) == (255, 255, 255, 255) and f.getpixel((0, 0))[3] == 0
    d = tmp_path / "f"; d.mkdir(); im.save(d / "a.png"); Image.new("RGBA", (5, 5), (0, 0, 0, 0)).save(d / "b.png")
    sprite_fx.main([str(d), "-o", str(tmp_path / "o"), "--outline", "2", "--shadow", "1,1,0.4,1", "--flash"])
    assert sorted(os.listdir(tmp_path / "o")) == ["a.png", "a_flash.png", "b.png", "b_flash.png"]
    pad2 = sprite_fx.pad_for(2, (1, 1, 0.4, 1))
    assert Image.open(tmp_path / "o" / "a.png").size == (8 + 2 * pad2, 8 + 2 * pad2)
    assert sprite_fx.parse_color("#fff1e8") == (255, 241, 232, 255)
    assert sprite_fx.parse_color("fff1e8") == (255, 241, 232, 255)
    with pytest.raises(SystemExit):
        sprite_fx.parse_color("red")
    sprite_fx.main([str(d / "a.png"), "-o", str(tmp_path / "hash"), "--outline", "1", "--outline-color", "#fff1e8"])
    hashed = Image.open(tmp_path / "hash" / "a.png")
    assert hashed.getpixel((sprite_fx.pad_for(1, None) + 1, sprite_fx.pad_for(1, None) + 2))[:3] == (255, 241, 232)


# ---------- glb-lod
def make_grid_glb(path, n=40):
    xs, ys = np.meshgrid(np.linspace(0, 4, n), np.linspace(0, 4, n))
    pos = np.stack([xs, np.sin(xs) * 0.2, ys], -1).reshape(-1, 3).astype(np.float32)
    nor = np.tile(np.array([0, 1, 0], np.float32), (len(pos), 1))
    uv = (np.stack([xs, ys], -1).reshape(-1, 2) / 4).astype(np.float32)
    idx = []
    for y in range(n - 1):
        for x in range(n - 1):
            a, b, c, d = y * n + x, y * n + x + 1, (y + 1) * n + x, (y + 1) * n + x + 1
            idx += [a, c, b, b, c, d]
    idx = np.array(idx, np.uint16)
    import io
    buf = io.BytesIO(); Image.new("RGB", (16, 8), (9, 9, 9)).save(buf, "PNG"); png = buf.getvalue()
    parts, views, off = [], [], 0
    for data, tgt in ((pos.tobytes(), 34962), (nor.tobytes(), 34962), (uv.tobytes(), 34962), (idx.tobytes(), 34963), (png, None)):
        pad = -off % 4; parts.append(b"\0" * pad); off += pad
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if tgt: v["target"] = tgt
        views.append(v); parts.append(data); off += len(data)
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"name": "grid", "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3, "material": 0}]}],
            "materials": [{"name": "m", "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
            "textures": [{"source": 0}], "images": [{"bufferView": 4, "mimeType": "image/png"}],
            "bufferViews": views, "buffers": [{"byteLength": off}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
                          {"bufferView": 1, "componentType": 5126, "count": len(pos), "type": "VEC3"},
                          {"bufferView": 2, "componentType": 5126, "count": len(pos), "type": "VEC2"},
                          {"bufferView": 3, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]}
    glb_lod.save_glb(path, gltf, b"".join(parts))
    return len(idx) // 3, pos


def test_glb_lod(tmp_path):
    p = tmp_path / "grid.glb"
    tris, pos = make_grid_glb(p)
    assert tris == 2 * 39 * 39
    glb_lod.main([str(p), "-o", str(tmp_path / "lod"), "--ratios", "0.5,0.1"])
    for r, name in ((0.5, "grid_lod1.glb"), (0.1, "grid_lod2.glb")):
        rep = gltf_inspect.inspect(str(tmp_path / "lod" / name))
        t = rep["totals"]["triangles"]
        assert 0.25 * tris * r < t <= 1.4 * r * tris, (r, t)
        assert not rep["warnings"], rep["warnings"]
        assert rep["textures"][0]["size"] == (16, 8)
        # bounds stay close to the original
        size = rep["bounds"]["size"]
        assert abs(size[0] - 4) < 0.5 and abs(size[2] - 4) < 0.5
    g, b = glb_lod.load_glb(str(tmp_path / "lod" / "grid_lod1.glb"))
    nrm = glb_lod.read_acc(g, b, g["meshes"][0]["primitives"][0]["attributes"]["NORMAL"])
    assert np.allclose(np.linalg.norm(nrm, axis=1), 1, atol=1e-3)
    # unsupported file is refused
    g2, b2 = glb_lod.load_glb(str(p)); g2["animations"] = [{"channels": [], "samplers": []}]
    glb_lod.save_glb(str(tmp_path / "anim.glb"), g2, b2)
    with pytest.raises(SystemExit):
        glb_lod.simplify(str(tmp_path / "anim.glb"), 0.5, str(tmp_path / "x.glb"))


# ---------- godot-import-presets
def test_godot_import_presets(tmp_path, capsys):
    proj = tmp_path / "proj"; (proj / "art/sprites").mkdir(parents=True); (proj / "audio").mkdir()
    Image.new("RGBA", (4, 4)).save(proj / "art/sprites/hero.png"); Image.new("RGBA", (4, 4)).save(proj / "art/ui.png")
    (proj / "audio/theme.wav").write_bytes(b"RIFF")
    (proj / "art/old.png").write_bytes(b""); (proj / "art/old.png.import").write_text("keep")
    rules = {"rules": [{"glob": "art/sprites/**/*.png", "preset": "pixel"}, {"glob": "art/old.png", "preset": "pixel"},
                       {"glob": "art/*.png", "preset": "ui"}, {"glob": "audio/*.wav", "preset": "wav-loop"}]}
    (tmp_path / "r.json").write_text(json.dumps(rules))
    godot_import_presets.main([str(proj), "-r", str(tmp_path / "r.json"), "--dry-run"])
    assert not (proj / "art/sprites/hero.png.import").exists()
    godot_import_presets.main([str(proj), "-r", str(tmp_path / "r.json")])
    t = (proj / "art/sprites/hero.png.import").read_text()
    assert 'importer="texture"' in t and 'source_file="res://art/sprites/hero.png"' in t
    assert "mipmaps/generate=false" in t and "compress/mode=0" in t
    assert "edit/loop_mode=2" in (proj / "audio/theme.wav.import").read_text()
    assert (proj / "art/old.png.import").read_text() == "keep"
    godot_import_presets.main(["--project-snippet"])
    assert "default_texture_filter=0" in capsys.readouterr().out


    # ** matches files in that folder (zero extra dirs) and in subfolders; * does not cross slashes
    deep = proj / "art/sprites/nested/x.png"; deep.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 4)).save(deep)
    rules2 = {"rules": [{"glob": "art/**/*.png", "preset": "pixel"}]}
    r2 = tmp_path / "r2.json"; r2.write_text(json.dumps(rules2))
    from godot_import_presets import glob_match, plan
    assert glob_match("art/ui.png", "art/**/*.png")
    assert glob_match("art/sprites/hero.png", "art/sprites/**/*.png")
    assert glob_match("art/sprites/nested/x.png", "art/**/*.png")
    assert not glob_match("art/sprites/hero.png", "art/*.png")
    assert glob_match("sfx/hit.wav", "sfx/**/*.wav")
    planned = {rel: preset for rel, preset, _ in plan(str(proj), rules2["rules"])}
    assert planned.get("art/ui.png") == "pixel"
    assert planned.get("art/sprites/hero.png") == "pixel"
    assert planned.get("art/sprites/nested/x.png") == "pixel"



# ---------- loop-finder
def test_loop_finder(tmp_path):
    sr = 22050
    t = np.arange(int(sr * 20)) / sr
    # 4 bars of a repeating pattern (period 2.0 s), preceded by a 3.3 s non-repeating intro
    pat = lambda tt: 0.4 * np.sin(2 * np.pi * 220 * tt) * (np.sin(np.pi * (tt % 2.0) / 2.0) ** 2) + 0.2 * np.sin(2 * np.pi * 330 * tt * (1 + 0.5 * ((tt % 2.0) > 1)))
    intro = 0.3 * np.sin(2 * np.pi * 97 * np.arange(int(3.3 * sr)) / sr) * np.linspace(1, 0, int(3.3 * sr))
    body = pat(np.arange(int(14 * sr)) / sr)
    x = np.concatenate([intro, body])[:, None].astype(np.float32)
    lp = loop_finder.find_loop(x, sr, window_s=0.5, min_len_s=2.0, tail_s=6.0, head_frac=0.6)
    assert lp["score"] > 0.9
    # loop length must be a multiple of the 2 s pattern period
    k = lp["length_s"] / 2.0
    assert abs(k - round(k)) < 0.02 and round(k) >= 1
    assert lp["start_s"] >= 3.2   # start lands inside the repeating body, not the intro
    seg = loop_finder.render_loop(x, lp)
    assert len(seg) == lp["end"] - lp["start"]
    src = tmp_path / "m.wav"; loop_finder.write_wav(str(src), x, sr)
    loop_finder.main([str(src), "-o", str(tmp_path / "o"), "--json", str(tmp_path / "l.json"), "--min-length", "2"])
    assert os.path.exists(tmp_path / "o" / "m_loop.wav") and "m.wav" in json.load(open(tmp_path / "l.json"))


# ---------- asset-viewer
def _check_js(html, tmp_path):
    s = html.index("<script>") + 8; e = html.index("</script>")
    js = tmp_path / "v.js"; js.write_text(html[s:e])
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_asset_viewer(tmp_path):
    d = tmp_path / "spr"; d.mkdir()
    for i in range(3): Image.new("RGBA", (10 + i, 12), (i * 80, 50, 50, 255)).save(d / f"s{i}.png")
    atlas_pack.main([str(d), "-o", str(tmp_path / "atlas")])
    asset_viewer.main(["atlas", str(tmp_path / "atlas.png"), str(tmp_path / "atlas.json"), "-o", str(tmp_path / "a.html")])
    html = (tmp_path / "a.html").read_text()
    data = json.loads(html.split("const DATA=")[1].split(";\nconst cv")[0])
    assert data["mode"] == "atlas" and {f["name"] for f in data["frames"]} == {"s0", "s1", "s2"}
    _check_js(html, tmp_path)
    g, _ = dungeon_gen.bsp(32, 20, 1); dungeon_gen.main(["--seed", "1", "--size", "32x20", "-o", str(tmp_path / "dg")])
    asset_viewer.main(["map", str(tmp_path / "dg.json"), "-o", str(tmp_path / "m.html")])
    md = json.loads((tmp_path / "m.html").read_text().split("const DATA=")[1].split(";\nconst cv")[0])
    assert md["w"] == 32 and md["h"] == 20 and len(md["data"]) == 640
    asset_viewer.main(["frames", str(d), "-o", str(tmp_path / "f.html")])
    fh = (tmp_path / "f.html").read_text(); _check_js(fh, tmp_path)
    assert "http://" not in fh.split("<script>")[0] and "fetch(" not in fh


# ---------- fleet-jobs
def test_fleet_jobs(tmp_path):
    (tmp_path / "s.csv").write_text("name,subject,size,variants\nhero,knight in blue armor,512x512,2\nslime,green slime,,\n")
    fleet_jobs.main(["qwen-image", str(tmp_path / "s.csv"), "--style", "pixel art, flat colours", "-o", str(tmp_path / "q.json")])
    q = json.load(open(tmp_path / "q.json"))
    assert q["model"] == "Qwen-Image 2.1" and q["target"] == "turbo" and q["status"] == "queued-not-launched"
    assert [i["name"] for i in q["items"]] == ["hero_v1", "hero_v2", "slime_v1"] and q["items"][0]["width"] == 512
    assert len({i["seed"] for i in q["items"]}) == 3
    (tmp_path / "c.csv").write_text("cue,mood,bpm,length_s,loop,notes\ntown,warm folk,90,60,yes,lute\nboss,tense,150,90,no,drums\n")
    fleet_jobs.main(["minimax-music", str(tmp_path / "c.csv"), "-o", str(tmp_path / "m.json")])
    m = json.load(open(tmp_path / "m.json"))
    assert "seamless loop" in m["items"][0]["prompt"] and "seamless loop" not in m["items"][1]["prompt"]
    fleet_jobs.main(["h3-video", "--turntable", "treasure_chest", "-o", str(tmp_path / "h.json")])
    h = json.load(open(tmp_path / "h.json"))
    assert len(h["items"]) == 3 and h["model"] == "H3 video"
    assert fleet_jobs.main(["validate", str(tmp_path / "q.json"), str(tmp_path / "m.json"), str(tmp_path / "h.json")]) == 0
    # same input -> same id (deterministic); items may mention 'atlas' without tripping validation
    assert fleet_jobs.jid("image.x", [1]) == fleet_jobs.jid("image.x", [1])
    for bad in ({"target": "sparky"}, {"target": "atlas"}, {"status": "running"}, {"constraints": {"huggingface_pull": True}}):
        j = json.loads(json.dumps(q)); j.update(bad)
        assert fleet_jobs.validate(j)
        with pytest.raises(SystemExit):
            fleet_jobs.write(j, str(tmp_path / "bad.json"))
    j = json.loads(json.dumps(q)); j["items"][0]["prompt"] = "texture atlas of a sparky robot"
    assert fleet_jobs.validate(j) == []
    json.dump({**q, "target": "sparky"}, open(tmp_path / "evil.json", "w"))
    assert fleet_jobs.main(["validate", str(tmp_path / "evil.json")]) == 1


def test_fleet_jobs_cannot_launch_anything():
    src = open(os.path.join(os.path.dirname(fleet_jobs.__file__), "fleet_jobs.py")).read()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import): mods |= {a.name.split(".")[0] for a in n.names}
        if isinstance(n, ast.ImportFrom): mods.add((n.module or "").split(".")[0])
    assert not mods & {"subprocess", "socket", "requests", "urllib", "http", "paramiko", "os_system", "asyncio", "ssl", "ftplib", "smtplib", "huggingface_hub"}
    assert "os.system" not in src and "Popen" not in src
