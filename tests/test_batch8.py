import csv, json, os, wave
import numpy as np
import pytest
from PIL import Image
import ase_json_import
from gst_errors import GstInputError
import tileset_gen, heightmap_tools, sfx_spectrogram, dialogue_stats, team_outline, obj_uv_unwrap, data_diff
import terrain_noise, terrain_erode, obj_to_glb, anim_meta


# ---------- ase-json-import
def ase(array=True):
    fr = [{"filename": f"hero {i}", "frame": {"x": i * 16, "y": 0, "w": 16, "h": 16}, "rotated": False, "trimmed": i == 2, "spriteSourceSize": {"x": 0, "y": 0, "w": 16, "h": 16},
           "sourceSize": {"w": 16, "h": 16}, "duration": d} for i, d in enumerate([100, 100, 200, 50, 50])]
    meta = {"image": "hero.png", "size": {"w": 80, "h": 16}, "frameTags": [{"name": "idle", "from": 0, "to": 1, "direction": "forward"}, {"name": "run", "from": 1, "to": 4, "direction": "pingpong"},
            {"name": "hit", "from": 2, "to": 3, "direction": "reverse"}], "slices": [{"name": "hurtbox"}]}
    return {"frames": fr if array else {f["filename"]: {k: v for k, v in f.items() if k != "filename"} for f in fr}, "meta": meta}


def test_ase_json_import(tmp_path):
    for array in (True, False):
        atlas, clips, slices = ase_json_import.convert(ase(array), once={"hit"})
        assert list(atlas["frames"])[2] == "hero 2" and atlas["frames"]["hero 2"]["trimmed"] is True and atlas["meta"]["size"] == {"w": 80, "h": 16}
        assert clips["idle"]["frames"] == ["hero 0", "hero 1"] and clips["idle"]["fps"] == 10.0 and clips["idle"]["loop"] is True
        assert clips["run"]["frames"] == ["hero 1", "hero 2", "hero 3", "hero 4", "hero 3", "hero 2"]          # pingpong: no doubled end frames
        assert clips["hit"]["frames"] == ["hero 3", "hero 2"] and clips["hit"]["loop"] is False and clips["hit"]["durations_ms"] == [50, 200] and clips["hit"]["duration"] == 0.25
        assert [s["name"] for s in slices] == ["hurtbox"]
    d = ase(); del d["frames"][0]["filename"]; a2, _, _ = ase_json_import.convert(d, "sheet"); assert "sheet_0" in a2["frames"]
    assert ase_json_import.expand(["a", "b"], "pingpong") == ["a", "b"] and ase_json_import.expand(["a"], "pingpong") == ["a"] and ase_json_import.expand(["a", "b", "c"], "pingpong_reverse") == ["c", "b", "a", "b"]
    d = ase(); d["meta"]["frameTags"][0]["to"] = 99
    with pytest.raises(GstInputError): ase_json_import.convert(d)
    d = ase(); d["frames"][1]["rotated"] = True
    a_rot, _, _ = ase_json_import.convert(d)
    assert a_rot["frames"]["hero 1"]["rotated"] is True and "rotated" not in a_rot["frames"]["hero 0"]
    d = ase(); d["meta"]["frameTags"] = []; assert list(ase_json_import.convert(d)[1]) == ["all"]
    json.dump(ase(), open(tmp_path / "h.json", "w")); ase_json_import.main([str(tmp_path / "h.json"), "-o", str(tmp_path / "out"), "--phaser", str(tmp_path / "ph.json"), "--atlas-key", "hero"])
    assert json.load(open(tmp_path / "ph.json"))["anims"][0]["frames"][0]["key"] == "hero" and "clips" in json.load(open(tmp_path / "out.clips.json"))
    import atlas_validate; Image.new("RGBA", (80, 16), (255, 0, 0, 255)).save(tmp_path / "hero.png")
    assert not [x for x in atlas_validate.validate(json.load(open(tmp_path / "out.json")), Image.open(tmp_path / "hero.png"), padding=0) if x["level"] == "error"]    # output is a valid atlas


# ---------- tileset-gen
def test_tileset_gen_masks():
    assert len(tileset_gen.CANON) == 47 and len(tileset_gen.LOOKUP) == 256 and set(tileset_gen.LOOKUP) == set(range(47))
    assert tileset_gen.canon(tileset_gen.NE) == 0                                                     # lone diagonal does not count
    assert tileset_gen.canon(tileset_gen.NE | tileset_gen.N | tileset_gen.E) == tileset_gen.NE | tileset_gen.N | tileset_gen.E
    assert tileset_gen.CANON[0] == 0 and tileset_gen.CANON[-1] == 255
    g = [[1, 1, 0], [1, 1, 1], [0, 1, 0]]; m = tileset_gen.mask_for(g, 1, 1)
    assert m == tileset_gen.N | tileset_gen.NE * 0 | tileset_gen.E | tileset_gen.S | tileset_gen.W | tileset_gen.NW and not m & tileset_gen.NE and not m & tileset_gen.SE
    assert tileset_gen.mask_for(g, 0, 0) == tileset_gen.E | tileset_gen.S | tileset_gen.SE                    # off-grid neighbours are empty


def test_tileset_gen_render(tmp_path):
    sheet, meta = tileset_gen.build(16, 4, "#00ff00", "#ff0000", None)
    assert sheet.size == (128, 96) and meta["count"] == 47 and meta["columns"] == 8
    def tile(mask): i = tileset_gen.LOOKUP[mask]; t = meta["tiles"][str(i)]; return np.array(sheet.crop((t["x"], t["y"], t["x"] + 16, t["y"] + 16)))
    full = tile(255); assert (full[..., :3] == (0, 255, 0)).all()                                       # fully surrounded: all inner terrain
    iso = tile(0); assert (iso[8, 8, :3] == (0, 255, 0)).all() and (iso[0, 0, :3] == (255, 0, 0)).all() and (iso[2, 8, :3] == (255, 0, 0)).all()   # island: inset all round
    n_missing = tile(255 & ~tileset_gen.N & ~tileset_gen.NE & ~tileset_gen.NW)
    assert (n_missing[:4, 8, :3] == (255, 0, 0)).all() and (n_missing[4, 8, :3] == (0, 255, 0)).all() and (n_missing[8, 0, :3] == (0, 255, 0)).all()   # top edge recedes only
    inner = tile(255 & ~tileset_gen.NE)
    assert (inner[0, 15, :3] == (255, 0, 0)).all() and (inner[0, 0, :3] == (0, 255, 0)).all() and (inner[4, 15, :3] == (0, 255, 0)).all()               # one notched corner
    assert (np.array(sheet)[-16:, -16:, 3] == 0).all()                                                  # the 48th slot is empty
    s2, _ = tileset_gen.build(16, 4, "#00ff00", "none", "#000000"); t0 = np.array(s2.crop((0, 0, 16, 16)))
    assert t0[0, 0, 3] == 0 and tuple(t0[4, 8, :3]) == (0, 0, 0) and tuple(t0[8, 8, :3]) == (0, 255, 0)  # outline sits on the boundary, outside is transparent
    Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(tmp_path / "tex.png")
    s3, _ = tileset_gen.build(16, None, str(tmp_path / "tex.png"), "#ffffff"); assert tuple(np.array(s3)[8, 8, :3]) == (10, 20, 30)
    tileset_gen.main(["-o", str(tmp_path / "ts"), "--tile", "8"]); assert json.load(open(tmp_path / "ts.json"))["count"] == 47
    with pytest.raises(SystemExit): tileset_gen.build(16, 9)


# ---------- heightmap-tools
def test_heightmap_tools(tmp_path):
    h = terrain_noise.fbm(64, seed=4, tile=True)
    b = heightmap_tools.blur(h, 2.0, wrap=True); assert abs(b.sum() - h.sum()) < 1e-6 and np.abs(np.diff(b)).max() < np.abs(np.diff(h)).max()
    assert np.allclose(heightmap_tools.blur(h, 0), h)
    sp = np.zeros((9, 9)); sp[4, 4] = 1; bs = heightmap_tools.blur(sp, 1.0); assert abs(bs.sum() - 1) < 1e-6 and bs[4, 4] == bs.max() and np.allclose(bs, bs.T)
    ramp = np.tile(np.linspace(0, 1, 101), (3, 1)); t = heightmap_tools.terrace(ramp, 5, 12.0)
    frac = (t * 5) % 1.0; near = np.minimum(frac, 1 - frac); assert (near < 0.1).mean() > 0.7 and np.all(np.diff(t[0]) >= -1e-12) and t.min() >= 0 and t.max() <= 1     # clustered on plateaus, monotonic
    assert np.allclose(heightmap_tools.terrace(ramp, 5, 0), ramp, atol=1e-9)
    assert heightmap_tools.clamp(np.array([0, 0.2, 0.5, 0.9]), 0.2, 0.6).tolist() == [0, 0, 0.75, 1]
    with pytest.raises(SystemExit): heightmap_tools.clamp(h, 0.5, 0.5)
    n = heightmap_tools.normalize(h * 0.3 + 0.2); assert n.min() == 0 and abs(n.max() - 1) < 1e-12 and heightmap_tools.normalize(np.ones((3, 3))).max() == 0
    r = heightmap_tools.resize(h, 33); assert r.shape == (33, 33) and abs(r.mean() - h.mean()) < 0.03
    flat = heightmap_tools.slope(np.zeros((8, 8))); assert flat.max() == 0
    ramp2 = np.tile(np.linspace(0, 1, 64), (64, 1)); s = heightmap_tools.slope(ramp2, height_scale=63, cell=1.0); assert abs(s[32, 32] - 45) < 0.5          # rises 1 per pixel = 45 degrees
    terrain_erode.save16(h, str(tmp_path / "h.png"))
    for op, extra in (("blur", ["--sigma", "1.5", "--wrap"]), ("terrace", ["--steps", "4"]), ("clamp", ["--lo", "0.2", "--hi", "0.8"]), ("normalize", []), ("invert", []), ("resize", ["--size", "33"]), ("slope", [])):
        assert heightmap_tools.main([op, str(tmp_path / "h.png"), "-o", str(tmp_path / f"{op}.png")] + extra) == 0 and (tmp_path / f"{op}.png").exists()
    assert Image.open(tmp_path / "resize.png").size == (33, 33) and Image.open(tmp_path / "blur.png").mode == "I;16" and Image.open(tmp_path / "slope.png").mode == "L"
    inv = terrain_erode.load(str(tmp_path / "invert.png")); assert np.abs(inv - (1 - h)).max() < 3e-5
    assert heightmap_tools.main(["stats", str(tmp_path / "h.png")]) == 0


# ---------- sfx-spectrogram
def _wav(path, x, sr=16000):
    with wave.open(str(path), "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def test_sfx_spectrogram(tmp_path):
    sr = 16000; t = np.arange(sr * 2) / sr; x = 0.5 * np.sin(2 * np.pi * 2000 * t)
    S = sfx_spectrogram.stft_db(x, 1024); peak_bin = S.mean(1).argmax(); assert abs(peak_bin * sr / 1024 - 2000) < sr / 1024 * 1.5 and abs(S.max() - 20 * np.log10(0.5)) < 0.5
    rep = sfx_spectrogram.analyse(x, sr); assert rep["clipped_ranges_s"] == [] and rep["peak"] == 0.5 and rep["seconds"] == 2.0
    y = np.concatenate([x[:sr], np.zeros(sr // 2), np.clip(x[:sr // 2] * 4, -1, 1)]); r = sfx_spectrogram.analyse(y, sr)
    assert len(r["clipped_ranges_s"]) >= 1 and r["clipped_ranges_s"][0][0] >= 1.5 - 0.01 and any(abs(a - 1.0) < 0.02 for a, _ in r["silent_ranges_s"])
    img = sfx_spectrogram.render(x, sr, width=200, height=100, max_freq=4000); arr = np.array(img)
    assert img.size == (200, 100 + 64)
    top = arr[:100]
    bright_row = int(np.argmax(top[..., 0].mean(1))); assert 35 <= bright_row <= 65      # 2 kHz in a 0..4 kHz view sits mid-height
    wav = arr[100:]; assert (wav[..., 2] > 200).any() and not ((wav[..., 0] > 200) & (wav[..., 1] < 80)).any()      # no red (clip) columns in a clean file
    lg = np.array(sfx_spectrogram.render(x, sr, width=200, height=100, log=True))[:100]; row = int(np.argmax(lg[..., 0].mean(1))); assert 15 <= row <= 45           # 2 kHz on a 40 Hz..8 kHz log axis is in the upper third
    imgc = np.array(sfx_spectrogram.render(y, sr, width=200)); assert ((imgc[256:, :, 0] > 200) & (imgc[256:, :, 1] < 80)).any()
    _wav(tmp_path / "a.wav", x); _wav(tmp_path / "c.wav", np.clip(y * 1.5, -1, 1))
    assert sfx_spectrogram.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "o"), "--json", str(tmp_path / "r.json"), "--fail-on-clip"]) == 0 and (tmp_path / "o" / "a_spec.png").exists()
    assert sfx_spectrogram.main([str(tmp_path / "c.wav"), "-o", str(tmp_path / "o"), "--fail-on-clip"]) == 1
    _wav(tmp_path / "short.wav", np.sin(np.arange(300) * 0.3) * 0.2); assert sfx_spectrogram.main([str(tmp_path / "short.wav"), "-o", str(tmp_path / "o")]) == 0     # shorter than one FFT window


# ---------- dialogue-stats
YARN = """title: Start
---
Ava: Welcome to the station, traveller. Please mind the step. #line:a1
Ava: Second line.
Narration without a speaker here.
-> Ask about the station
    <<jump Station>>
-> Leave
    <<jump End>>
===
title: Station
---
Bo: It is old. #line:b1
<<jump End>>
===
title: End
---
Ava: Bye. #line:c1
<<stop>>
===
"""


def test_dialogue_stats(tmp_path):
    p = tmp_path / "s.yarn"; p.write_text(YARN)
    rows, nodes = dialogue_stats.collect([str(p)]); s = dialogue_stats.stats(rows, nodes, top=2, max_words=8)
    assert s["lines"] == len(rows) >= 5 and s["nodes"] == 3 and s["words"] == sum(r["words"] for r in rows)
    sp = {x["speaker"]: x for x in s["speakers"]}; assert sp["Ava"]["lines"] == 3 and sp["Bo"]["lines"] == 1 and "(narration)" in sp and abs(sum(x["share_pct"] for x in s["speakers"]) - 100) < 0.5
    assert s["longest_lines"][0]["words"] == max(r["words"] for r in rows) and len(s["longest_lines"]) == 2
    assert s["lines_without_id"] == sum(1 for r in rows if not r["has_id"]) and s["lines_without_id"] >= 2
    assert s["most_branching"][0] == {"node": "Start", "choices": 2} and "End" in s["terminal_nodes"] and s["avg_branching"] == 1.5
    assert any(x["words"] > 8 for x in s["over_max_words"]) and "| Ava |" in dialogue_stats.markdown(s)
    assert dialogue_stats.main([str(p), "--md", str(tmp_path / "s.md"), "--json", str(tmp_path / "s.json")]) == 0 and json.load(open(tmp_path / "s.json"))["lines"] == s["lines"]
    assert dialogue_stats.main([str(p), "--max-words", "8", "--fail-long"]) == 1 and dialogue_stats.main([str(p), "--max-words", "50", "--fail-long"]) == 0
    ink = tmp_path / "t.ink"; ink.write_text("=== start ===\nBo: Hello there.\n* [Go] -> end\n=== end ===\nBo: Bye.\n-> END\n")
    r2, n2 = dialogue_stats.collect([str(ink)]); assert len(r2) >= 2 and "end" in n2


# ---------- team-outline
def sprite():
    a = np.zeros((10, 10, 4), np.uint8); a[2:8, 2:8] = (200, 180, 120, 255); a[4:6, 4:6] = (255, 0, 255, 255); a[5, 5] = (128, 0, 128, 255)
    a[3, 3] = (0, 0, 0, 255); return Image.fromarray(a, "RGBA")


def test_team_outline():
    img = sprite(); a = np.array(img)
    em = team_outline.edge_mask(a); assert em[2, 2] and em[7, 4] and not em[4, 4] and not em[0, 0] and em.sum() == 20
    r = np.array(team_outline.recolor(img, "#ff0000", edge=True)); assert tuple(r[2, 4, :3]) == (255, 0, 0) and tuple(r[4, 3, :3]) == (200, 180, 120) and (r[..., 3] == a[..., 3]).all()
    m = np.array(team_outline.recolor(img, "#0000ff", match="#000000", tol=10)); assert tuple(m[3, 3, :3]) == (0, 0, 255) and tuple(m[2, 2, :3]) == (200, 180, 120)
    k = np.array(team_outline.recolor(img, "#00c800", key="#ff00ff")); assert tuple(k[4, 4, :3]) == (0, 200, 0) and 90 < k[5, 5, 1] < 110 and k[5, 5, 0] == 0 and k[5, 5, 2] == 0     # shading kept: half-bright key -> half-bright green
    assert tuple(k[2, 4, :3]) == (200, 180, 120)                                                           # non-key colours untouched
    assert (np.array(team_outline.recolor(img, "#ff0000", edge=True)) != np.array(team_outline.recolor(img, "#0000ff", edge=True))).any()


def test_team_outline_cli(tmp_path):
    sprite().save(tmp_path / "unit.png")
    assert team_outline.main([str(tmp_path / "unit.png"), "-o", str(tmp_path / "o"), "--team", "red=#ff0000", "--team", "blue=#0000ff", "--edge", "--key", "#ff00ff"]) == 0
    assert sorted(os.listdir(tmp_path / "o")) == ["unit_blue.png", "unit_red.png"]
    with pytest.raises(SystemExit): team_outline.main([str(tmp_path / "unit.png"), "-o", str(tmp_path / "o"), "--team", "red=#ff0000"])


# ---------- obj-uv-unwrap
CUBE = ["# cube", "mtllib c.mtl"] + [f"v {x} {y} {z}" for x in (0, 2) for y in (0, 2) for z in (0, 2)] + ["vn 0 0 1", "o cube", "usemtl m",
        "f 1 2 4 3", "f 5 7 8 6", "f 1 5 6 2", "f 3 4 8 7", "f 1 3 7 5", "f 2 6 8 4"]


def test_obj_uv_unwrap_box(tmp_path):
    p = tmp_path / "c.obj"; p.write_text("\n".join(CUBE) + "\n")
    lines, V = obj_uv_unwrap.parse(str(p)); text, n = obj_uv_unwrap.unwrap(lines, V, "box")
    out = text.splitlines(); vts = [list(map(float, l.split()[1:3])) for l in out if l.startswith("vt ")]; faces = [l.split()[1:] for l in out if l.startswith("f ")]
    assert n == len(vts) == 24 and len(faces) == 6 and all(0 <= u <= 1 and 0 <= v <= 1 for u, v in vts)
    assert out.index(next(l for l in out if l.startswith("vt "))) < out.index("o cube") + 1 and "mtllib c.mtl" in out and "usemtl m" in out        # structure kept, vt before faces
    pos = [[int(t.split("/")[0]) for t in f] for f in faces]; assert pos == [[1, 2, 4, 3], [5, 7, 8, 6], [1, 5, 6, 2], [3, 4, 8, 7], [1, 3, 7, 5], [2, 6, 8, 4]]       # positions untouched
    boxes = []
    for f in faces:
        uv = np.array([vts[int(t.split("/")[1]) - 1] for t in f]); boxes.append((uv.min(0), uv.max(0)))
        assert abs((uv.max(0) - uv.min(0)).max() - (uv.max(0) - uv.min(0)).min()) < 1e-6                         # square faces stay square: uniform scale
    for i in range(6):
        for j in range(i + 1, 6): assert (boxes[i][1] <= boxes[j][0] + 1e-9).any() or (boxes[j][1] <= boxes[i][0] + 1e-9).any(), (i, j)         # islands do not overlap
    q = tmp_path / "c2.obj"; q.write_text(text)
    with pytest.raises(SystemExit): obj_uv_unwrap.main([str(q), "-o", str(tmp_path / "x.obj")])
    assert obj_uv_unwrap.main([str(q), "-o", str(tmp_path / "y.obj"), "--force"]) == 0
    g = obj_to_glb.convert(str(tmp_path / "y.obj")) if hasattr(obj_to_glb, "convert") else None; assert g is not None            # still loads through obj-to-glb


def test_obj_uv_unwrap_planar_and_normals(tmp_path):
    obj = ["v 0 0 0", "v 4 0 0", "v 4 0 2", "v 0 0 2", "vn 0 1 0", "f 1//1 4//1 3//1 2//1"]
    lines, V = list(obj), np.array([[0, 0, 0], [4, 0, 0], [4, 0, 2], [0, 0, 2]], float)
    text, n = obj_uv_unwrap.unwrap(lines, V, "planar", "y"); out = text.splitlines()
    assert n == 4 and next(l for l in out if l.startswith("f ")).split()[1].startswith("1/") and "//" not in next(l for l in out if l.startswith("f ")) and next(l for l in out if l.startswith("f ")).split()[1].endswith("/1")
    uvs = sorted(tuple(map(float, l.split()[1:3])) for l in out if l.startswith("vt ")); assert uvs[0] == (0.0, 0.0) and uvs[-1] == (1.0, 1.0) or uvs[-1][0] == 1.0
    s2, n2 = obj_uv_unwrap.unwrap(lines, V, "box"); assert n2 == 4                                                                # a flat quad: one island
    f = tmp_path / "q.obj"; f.write_text("\n".join(obj) + "\n"); assert obj_uv_unwrap.main([str(f), "-o", str(tmp_path / "o.obj"), "--mode", "planar", "--axis", "y"]) == 0


# ---------- data-diff
def test_data_diff(tmp_path):
    old = [{"id": "sword", "dmg": "10", "name": "Sword", "cost": "100"}, {"id": "bow", "dmg": "8", "name": "Bow", "cost": "80"}, {"id": "axe", "dmg": "0", "name": "Axe", "cost": "50"}, {"id": "gone", "dmg": "1", "name": "G", "cost": "1"}]
    new = [{"id": "sword", "dmg": "12", "name": "Sword", "cost": "100"}, {"id": "bow", "dmg": "8", "name": "Longbow", "cost": "81"}, {"id": "axe", "dmg": "5", "name": "Axe", "cost": "50"}, {"id": "spear", "dmg": "9", "name": "Spear", "cost": "70"}]
    d = data_diff.diff(old, new, "id")
    assert d["added"] == ["spear"] and d["removed"] == ["gone"] and sorted(d["changed"]) == ["axe", "bow", "sword"]
    assert d["changed"]["sword"] == {"dmg": {"old": "10", "new": "12", "pct": 20.0}} and d["changed"]["bow"]["name"]["pct"] is None and d["changed"]["bow"]["cost"]["pct"] == 1.25
    assert d["changed"]["axe"]["dmg"]["pct"] is None                                                       # from zero: no percentage
    assert d["fields_changed"] == {"dmg": 2, "cost": 1, "name": 1} or d["fields_changed"]["dmg"] == 2
    assert "cost" not in data_diff.diff(old, new, "id", min_pct=5)["changed"].get("bow", {}) and "bow" in data_diff.diff(old, new, "id", min_pct=5)["changed"]
    assert "dmg" not in data_diff.diff(old, new, "id", ignore={"dmg"})["changed"].get("sword", {}) and list(data_diff.diff(old, new, "id", only={"name"})["changed"]) == ["bow"]
    assert data_diff.diff(old, old, "id")["changed"] == {} and data_diff.diff([{"id": "a", "v": 1}, {"id": "a", "v": 2}], [], "id")["duplicate_keys"]["old"] == ["a"]
    assert data_diff.diff([{"id": "a", "v": 1}], [{"id": "a", "v": 1.0}], "id")["changed"] == {}           # 1 vs 1.0 is not a change
    assert data_diff.diff([{"id": "a", "v": True}], [{"id": "a", "v": False}], "id")["changed"]["a"]["v"]["pct"] is None
    with open(tmp_path / "o.csv", "w", newline="") as f: w = csv.DictWriter(f, fieldnames=list(old[0])); w.writeheader(); w.writerows(old)
    json.dump(new, open(tmp_path / "n.json", "w"))                                                          # CSV vs JSON works
    assert data_diff.main([str(tmp_path / "o.csv"), str(tmp_path / "n.json"), "--key", "id", "--md", str(tmp_path / "d.md"), "--json", str(tmp_path / "d.json")]) == 0
    assert "| sword |" in open(tmp_path / "d.md").read() and json.load(open(tmp_path / "d.json"))["added"] == ["spear"]
    assert data_diff.main([str(tmp_path / "o.csv"), str(tmp_path / "n.json"), "--key", "id", "--fail-on-removed"]) == 1 and data_diff.main([str(tmp_path / "o.csv"), str(tmp_path / "n.json"), "--key", "id", "--fail-on-diff"]) == 1
    assert data_diff.main([str(tmp_path / "o.csv"), str(tmp_path / "o.csv"), "--key", "id", "--fail-on-diff"]) == 0
