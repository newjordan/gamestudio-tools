import csv, json, math, os, struct, wave
import numpy as np
import pytest
from PIL import Image, ImageFont
import alpha_bleed, sprite_shadow, map_reach, loc_fit, loop_xfade, sfx_mix, collider_preview, onion_skin
import audio_tidy, wav_loop_meta, tile_colliders


# ---------- alpha-bleed
def test_alpha_bleed(tmp_path):
    a = np.zeros((9, 9, 4), np.uint8); a[4, 4] = (200, 50, 10, 255); a[4, 5] = (200, 50, 10, 128); a[0, 0] = (1, 2, 3, 0)
    im = Image.fromarray(a, "RGBA"); out, st = alpha_bleed.bleed(im, distance=2); o = np.array(out)
    assert (o[..., 3] == a[..., 3]).all()                                                                       # alpha never changes
    assert (o[4, 4] == a[4, 4]).all() and (o[4, 5] == a[4, 5]).all()                                           # opaque and semi-transparent pixels untouched
    assert tuple(o[4, 3][:3]) == (200, 50, 10) and tuple(o[2, 2][:3]) == (200, 50, 10) and tuple(o[2, 7][:3]) == (200, 50, 10)          # two passes reach two pixels out (also diagonally)
    assert tuple(o[0, 0][:3]) == (1, 2, 3) and tuple(o[0, 4][:3]) == (0, 0, 0)                                  # beyond the distance nothing is rewritten
    assert st["passes"] == 2 and st["pixels_filled"] == int((o[..., :3] != a[..., :3]).any(-1).sum())
    full, st2 = alpha_bleed.bleed(im, distance=0); assert tuple(np.array(full)[0, 8][:3]) == (200, 50, 10) and st2["passes"] == 4
    # the point: with plain (non-premultiplied) bilinear filtering a black transparent neighbour darkens the edge, a bled one does not
    solid = np.zeros((1, 8, 4), np.uint8); solid[:, :4] = (255, 255, 255, 255)
    def edge_rgb(arr): mid = (arr[0, 3].astype(float) + arr[0, 4].astype(float)) / 2; return mid[:3]               # texel halfway between the last opaque and the first transparent pixel
    assert edge_rgb(solid).max() == pytest.approx(127.5) and edge_rgb(np.array(alpha_bleed.bleed(Image.fromarray(solid, "RGBA"), 4)[0])).min() == 255
    src = tmp_path / "s.png"; im.save(src); assert alpha_bleed.main([str(src), "-o", str(tmp_path / "o.png")]) == 0 and Image.open(tmp_path / "o.png").size == (9, 9)
    assert alpha_bleed.main([str(tmp_path), "-o", str(tmp_path / "outdir"), "--distance", "3"]) == 0 and (tmp_path / "outdir" / "s.png").exists()
    th, _ = alpha_bleed.bleed(im, distance=3, threshold=128); assert tuple(np.array(th)[4, 5][:3]) == (200, 50, 10) and np.array(th)[4, 5, 3] == 128           # alpha 128 counts as transparent but keeps its alpha
    with pytest.raises(SystemExit): alpha_bleed.main([str(tmp_path / "missing.png"), "-o", str(tmp_path / "x")])


# ---------- sprite-shadow
def sprite(w=10, h=10, box=(2, 2, 8, 8), a=255):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); im.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (255, 0, 0, a)), box[:2]); return im


def test_sprite_shadow_drop():
    outs, pad = sprite_shadow.add_shadow([sprite()], "drop", dx=3, dy=2, blur=0, opacity=0.5)
    assert pad == (0, 0, 3, 2) and outs[0].size == (13, 12)
    o = np.array(outs[0]); assert tuple(o[4, 4]) == (255, 0, 0, 255)                                         # sprite still on top
    assert tuple(o[9, 10]) == (0, 0, 0, 128) and o[1, 1, 3] == 0                                              # sprite pixel (7,7) casts its shadow at (10, 9); an untouched corner stays transparent
    kept, _ = sprite_shadow.add_shadow([sprite()], "drop", dx=3, dy=2, blur=0, keep_size=True); assert kept[0].size == (10, 10)
    blurred, bp = sprite_shadow.add_shadow([sprite()], "drop", dx=0, dy=0, blur=2, opacity=1.0); assert bp == (6, 6, 6, 6) and blurred[0].size == (22, 22)
    col, _ = sprite_shadow.add_shadow([sprite()], "drop", dx=3, dy=0, blur=0, color="#0000ff", opacity=1.0); assert tuple(np.array(col[0])[4, 9]) == (0, 0, 255, 255)


def test_sprite_shadow_contact_and_frames():
    a, b = sprite(box=(2, 2, 8, 8)), sprite(box=(1, 0, 9, 6))                       # frames with different feet positions
    outs, pad = sprite_shadow.add_shadow([a, b], "contact", dx=0, dy=1, blur=0, opacity=1.0, width_scale=1.0, squash=0.5)
    assert outs[0].size == outs[1].size and pad[3] > 0                                   # one common canvas for all frames
    L, T, R, B = pad
    for out, box in ((outs[0], (2, 2, 8, 8)), (outs[1], (1, 0, 9, 6))):
        o = np.array(out); cx = L + (box[0] + box[2]) / 2; fy = T + box[3] + 1
        assert o[int(fy), int(cx), 3] == 255 and tuple(o[int(fy), int(cx)][:3]) == (0, 0, 0)                  # ellipse centre sits just under the feet
        assert o[int(fy) - 1, int(cx), 3] == 255                                                                # and extends up beside the feet line
    assert pad == (0, 0, 0, 1)                                                                                 # only one extra row below was needed
    # transparent frames do not crash, and --keep-size crops back
    empty = Image.new("RGBA", (6, 6), (0, 0, 0, 0)); e, _ = sprite_shadow.add_shadow([empty], "contact"); assert e[0].size == (6, 6) and e[0].getbbox() is None
    k, _ = sprite_shadow.add_shadow([a], "contact", keep_size=True); assert k[0].size == a.size


def test_sprite_shadow_cli(tmp_path):
    for i in range(2): sprite().save(tmp_path / f"f{i}.png")
    assert sprite_shadow.main([str(tmp_path / "f0.png"), str(tmp_path / "f1.png"), "-o", str(tmp_path / "out"), "--dx", "2", "--dy", "2", "--blur", "0"]) == 0
    assert Image.open(tmp_path / "out" / "f0.png").size == (12, 12) and Image.open(tmp_path / "out" / "f1.png").size == (12, 12)
    assert sprite_shadow.main([str(tmp_path / "f0.png"), "-o", str(tmp_path / "one.png"), "--mode", "contact"]) == 0 and (tmp_path / "one.png").exists()


# ---------- map-reach
def rmap(rows, objects=(), solid_rows=None):
    h, w = len(rows), len(rows[0]); ground = [1 if c != "." else 0 for r in rows for c in r]; solid = [1 if c == "#" else 0 for r in rows for c in r]
    layers = [{"type": "tilelayer", "name": "ground", "width": w, "height": h, "data": [1] * (w * h)}, {"type": "tilelayer", "name": "walls", "width": w, "height": h, "data": solid},
              {"type": "objectgroup", "name": "obj", "objects": list(objects)}]
    return {"type": "map", "width": w, "height": h, "tilewidth": 16, "tileheight": 16, "layers": layers}


def pt(i, name, tx, ty, typ=""): return {"id": i, "name": name, "type": typ, "x": tx * 16 + 8, "y": ty * 16 + 8, "point": True, "width": 0, "height": 0}


MAP = ["....#....",
       ".s.....k.",
       "....#....",
       "#########",
       "....#.d..",
       "..e.#....",
       "....#...."]


def test_map_reach():
    m = rmap(MAP, [pt(1, "spawn", 1, 1), pt(2, "key", 7, 1, "key"), pt(3, "door", 6, 4, "door"), pt(4, "exit", 2, 5, "exit")])
    rep, walk, seen = map_reach.analyze(m, solid_layer="walls", require=["exit"])
    assert rep["start"] == [1, 1] and rep["start_from"] == "spawn" and rep["walkable"] == 49 and rep["reachable"] == 25         # top half: 27 cells minus two wall cells; the gap at (4,1) joins its two rooms
    assert [i["tiles"] for i in rep["islands"]] == [12, 12] and {tuple(i["bbox"]) for i in rep["islands"]} == {(0, 4, 3, 6), (5, 4, 8, 6)}     # the bottom half is cut off by the solid row
    by = {o["name"]: o for o in rep["objects"]}; assert by["key"]["reachable"] and not by["door"]["reachable"] and not by["exit"]["reachable"]
    assert [o["name"] for o in rep["required_unreachable"]] == ["exit"]
    assert not walk[0, 4] and walk[1, 4] and walk[0, 3] and not seen[4, 2]
    # diagonal movement cannot squeeze between two solids touching at a corner
    dm = rmap(["s#", "#."]); r, _, _ = map_reach.analyze(dm, (0, 0), solid_layer="walls", diagonal=True); assert r["reachable"] == 1
    free = rmap(["s.", ".."]); r, _, _ = map_reach.analyze(free, (0, 0), solid_layer="walls", diagonal=True); assert r["reachable"] == 4
    # adjacent objects, solid ids, ground layer, tile objects, bad start
    chest = rmap(["s#.", "...", "..."], [{"id": 1, "name": "chest", "type": "chest", "x": 16, "y": 0, "width": 16, "height": 16}]); r, _, _ = map_reach.analyze(chest, (0, 0), solid_layer="walls")
    assert not r["objects"][0]["reachable"] and r["objects"][0]["on_solid"]; r, _, _ = map_reach.analyze(chest, (0, 0), solid_layer="walls", adjacent=True); assert r["objects"][0]["reachable"]
    ids = rmap(["s.."]); ids["layers"][0]["data"] = [1, 7, 1]; r, _, _ = map_reach.analyze(ids, (0, 0), solid_ids=[7]); assert r["reachable"] == 1
    gr = rmap(["s.."]); gr["layers"][0]["data"] = [1, 1, 0]; r, _, _ = map_reach.analyze(gr, (0, 0), ground_layer="ground"); assert r["reachable"] == 2 and r["walkable"] == 2
    assert map_reach.object_tile({"x": 32, "y": 48, "gid": 5, "width": 16, "height": 16}, 16, 16) == (2, 2) and map_reach.object_tile({"x": 0, "y": 0, "width": 32, "height": 32}, 16, 16) == (1, 1)
    with pytest.raises(SystemExit): map_reach.analyze(m, (4, 0), solid_layer="walls")               # start on a wall
    with pytest.raises(SystemExit): map_reach.analyze(rmap(["..."]), solid_layer="walls")           # no start object
    with pytest.raises(SystemExit): map_reach.analyze(m, (1, 1), solid_layer="nope")
    inf = dict(m, infinite=True)
    with pytest.raises(SystemExit): map_reach.analyze(inf, (1, 1), solid_layer="walls")


def test_map_reach_cli(tmp_path):
    m = rmap(MAP, [pt(1, "spawn", 1, 1), pt(4, "exit", 2, 5, "exit")]); json.dump(m, open(tmp_path / "m.json", "w"))
    base = [str(tmp_path / "m.json"), "--solid-layer", "walls", "--json", str(tmp_path / "r.json"), "--png", str(tmp_path / "r.png"), "--scale", "4"]
    assert map_reach.main(base) == 0 and map_reach.main(base + ["--require", "exit"]) == 1 and map_reach.main(base + ["--fail-on-islands"]) == 1 and map_reach.main(base + ["--fail-on-islands", "--min-island", "99"]) == 0
    img = Image.open(tmp_path / "r.png"); assert img.size == (36, 28) and tuple(img.getpixel((3 * 4 + 1, 1 * 4 + 1))[:3]) == (60, 170, 80) and tuple(img.getpixel((6 * 4 + 1, 5 * 4 + 1))[:3]) == (200, 60, 60)
    assert json.load(open(tmp_path / "r.json"))["start"] == [1, 1]
    assert map_reach.main([str(tmp_path / "m.json"), "--solid-layer", "walls", "--start", "7,0"]) == 0


# ---------- loc-fit
def test_loc_fit(tmp_path):
    font = ImageFont.load_default(16); w = lambda s: font.getlength(s)
    assert loc_fit.prepare("Hi {name}, you have %d <b>gold</b> [i]x[/i] 100%%", "00") == "Hi 00, you have 00 gold x 100%"
    assert loc_fit.wrap(font, "aaa bbb ccc", 10000) == ["aaa bbb ccc"]
    lines = loc_fit.wrap(font, "aa aa aa aa", w("aa aa") + 1); assert lines == ["aa aa", "aa aa"] and all(w(l) <= w("aa aa") + 1 for l in lines)
    assert loc_fit.wrap(font, "x" * 40, w("x" * 10) + 1) == ["x" * 10] * 4 and "".join(loc_fit.wrap(font, "x" * 40, w("x" * 10) + 1)) == "x" * 40
    cjk = "これはとても長い日本語の文章です" ; out = loc_fit.wrap(font, cjk, w(cjk) / 2 + 1); assert "".join(out) == cjk and len(out) >= 2
    rows = [{"id": "menu.play", "en": "Play", "de": "Spielen"}, {"id": "menu.quit", "en": "Quit", "de": "Beenden und zum Desktop zurückkehren"}, {"id": "title", "en": "A very long title that wraps", "de": ""}]
    lim = [("menu.*", w("Beenden") + 4, None), ("title", w("A very long title"), 2)]
    res = loc_fit.check(rows, ["en", "de"], font, lim, None); by = {(r["id"], r["lang"]): r for r in res}
    assert by[("menu.play", "en")]["fits"] and by[("menu.play", "de")]["fits"] and not by[("menu.quit", "de")]["fits"] and by[("menu.quit", "de")]["lines"] > 1
    assert ("title", "de") not in by and by[("title", "en")]["fits"] and by[("title", "en")]["lines"] == 2 and by[("menu.quit", "de")]["wrapped"].count("\n") >= 1
    assert loc_fit.check(rows, ["en"], font, [], None) == [] and len(loc_fit.check(rows, ["en"], font, [], 9999)) == 3
    assert [r["fits"] for r in loc_fit.check([{"id": "a", "en": "one\ntwo\nthree"}], ["en"], font, [], 9999, 2)] == [False]                    # explicit newlines count as lines
    csvp = tmp_path / "s.csv"; csvp.write_text("id,en,de\nmenu.play,Play,Spielen\nmenu.quit,Quit,Beenden und zum Desktop zurückkehren\n", encoding="utf-8")
    lp = tmp_path / "lim.csv"; lp.write_text(f"id,max_px,max_lines\nmenu.*,{w('Beenden') + 4},1\n", encoding="utf-8")
    base = [str(csvp), "--limits", str(lp), "--size", "16", "--out-csv", str(tmp_path / "o.csv"), "--json", str(tmp_path / "o.json")]
    assert loc_fit.main(base) == 1 and loc_fit.main(base + ["--only-failing", "--max-lines", "9"]) == 1 and loc_fit.main([str(csvp), "--limit-default", "9999"]) == 0
    assert any(r["id"] == "menu.quit" and r["fits"] == "False" for r in csv.DictReader(open(tmp_path / "o.csv", encoding="utf-8"))) and len(json.load(open(tmp_path / "o.json"))) == 4
    with pytest.raises(SystemExit): loc_fit.main([str(csvp)])


# ---------- loop-xfade
def wavs(path, x, sr=8000, bits=16): audio_tidy.write_wav(str(path), x, sr, bits)


def test_loop_xfade(tmp_path):
    sr = 8000; t = np.arange(sr * 2) / sr; x = (0.5 * np.sin(2 * np.pi * 437.3 * t))[:, None]; start, end = 4000, 12000 - 1 + 77              # loop length is not a whole number of cycles: a click
    before = loop_xfade.wrap_jump(x, start, end); y = loop_xfade.crossfade(x, start, end, 400); after = loop_xfade.wrap_jump(y, start, end)
    assert before > 3 and after < 1.5 and after < before / 3
    assert np.allclose(y[end], x[start - 1]) and np.allclose(y[:end - 399], x[:end - 399]) and np.allclose(y[end + 1:], x[end + 1:])             # only the loop tail changes
    mid = end - 200; wgt = np.cos(0.5 * np.pi * 200 / 400), np.sin(0.5 * np.pi * 200 / 400); assert y[mid, 0] == pytest.approx(wgt[0] * x[mid, 0] + wgt[1] * x[start - 400 + 199, 0])      # equal-power weights
    lin = loop_xfade.crossfade(x, start, end, 400, linear=True); assert lin[end - 399, 0] == pytest.approx(x[end - 399, 0] * (1 - 1 / 400) + x[start - 400, 0] / 400)
    for bad in ((0, 100, 50), (4000, 5000, 4500), (4000, 20000, 100), (100, 5000, 200)):
        with pytest.raises(SystemExit): loop_xfade.crossfade(x, bad[0], bad[1], bad[2])
    wavs(tmp_path / "a.wav", x, sr, 24)
    assert loop_xfade.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "o.wav"), "--start", str(start), "--end", str(end), "--fade-ms", "50"]) == 0
    data = open(tmp_path / "o.wav", "rb").read(); assert wav_loop_meta.read_loops(data)[0]["start"] == start and wav_loop_meta.read_loops(data)[0]["end"] == end
    z, sr2 = audio_tidy.read_wav(str(tmp_path / "o.wav")); assert sr2 == sr and len(z) == len(x) and wave.open(str(tmp_path / "o.wav")).getsampwidth() == 3 and loop_xfade.wrap_jump(z, start, end) < 2
    open(tmp_path / "m.wav", "wb").write(wav_loop_meta.set_loop(open(tmp_path / "a.wav", "rb").read(), start, end))                    # loop points taken from the smpl chunk
    assert loop_xfade.main([str(tmp_path / "m.wav"), "-o", str(tmp_path / "o2.wav"), "--fade-frames", "100"]) == 0
    with pytest.raises(SystemExit): loop_xfade.main([str(tmp_path / "a.wav"), "-o", str(tmp_path / "o3.wav")])
    st = np.concatenate([x, x * 0.5], 1); wavs(tmp_path / "s.wav", st, sr); assert loop_xfade.main([str(tmp_path / "s.wav"), "-o", str(tmp_path / "so.wav"), "--start", "4000", "--end", "9000"]) == 0 and audio_tidy.read_wav(str(tmp_path / "so.wav"))[0].shape[1] == 2


# ---------- sfx-mix
def tone(path, f, ms, amp=0.5, sr=8000, ch=1):
    t = np.arange(int(sr * ms / 1000)) / sr; x = amp * np.sin(2 * np.pi * f * t)[:, None]; audio_tidy.write_wav(str(path), np.repeat(x, ch, 1), sr)


def test_sfx_mix(tmp_path):
    tone(tmp_path / "a.wav", 200, 100); tone(tmp_path / "b.wav", 400, 50, 0.25)
    rec = {"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "a.wav"}, {"file": "b.wav", "offset_ms": 100, "gain_db": 6.0206}]}
    out, sr, rep = sfx_mix.mix(rec, str(tmp_path)); assert sr == 8000 and out.shape == (1200, 1) and rep["duration_s"] == 0.15 and rep["scale_db"] == 0
    a, _ = audio_tidy.read_wav(str(tmp_path / "a.wav")); b, _ = audio_tidy.read_wav(str(tmp_path / "b.wav"))
    assert np.allclose(out[:800], a, atol=1e-4) and np.allclose(out[800:], b * 2, atol=1e-3)                          # layers sit where the offsets say, gain applied
    ov = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "a.wav"}, {"file": "a.wav", "gain_db": -6.0206}]}, str(tmp_path))[0]; assert np.allclose(ov, a * 1.5, atol=1e-3)
    # peak control: scaled down when over, left alone when under, normalised up on request
    loud = sfx_mix.mix({"sample_rate": 8000, "peak_db": -6.0206, "layers": [{"file": "a.wav"}, {"file": "a.wav"}]}, str(tmp_path)); assert loud[2]["peak_db"] == pytest.approx(-6.02, abs=0.01) and loud[2]["scale_db"] < 0
    quiet = sfx_mix.mix({"sample_rate": 8000, "peak_db": -1, "layers": [{"file": "b.wav"}]}, str(tmp_path)); assert quiet[2]["scale_db"] == 0
    norm = sfx_mix.mix({"sample_rate": 8000, "peak_db": -1, "normalize": True, "layers": [{"file": "b.wav"}]}, str(tmp_path)); assert norm[2]["peak_db"] == pytest.approx(-1.0, abs=0.01)
    # fades, trim, reverse, pitch, tail
    f = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "tail_ms": 50, "layers": [{"file": "a.wav", "fade_in_ms": 25, "fade_out_ms": 25, "trim_ms": 80}]}, str(tmp_path))[0]
    assert len(f) == 640 + 400 and abs(f[0, 0]) < 1e-3 and np.abs(f[100:500]).max() > 0.45 and abs(f[639, 0]) < 0.02 and np.abs(f[700:]).max() == 0
    r = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "a.wav", "reverse": True}]}, str(tmp_path))[0]; assert np.allclose(r, a[::-1], atol=1e-4)
    up = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "a.wav", "pitch_semitones": 12}]}, str(tmp_path))[0]; assert abs(len(up) - 400) <= 1
    z = lambda v: np.sum(np.diff(np.sign(v[:, 0])) != 0); assert z(up) == pytest.approx(z(a), abs=3)                # octave up: the same number of cycles in half the time
    # filters: a 3 kHz tone through a 300 Hz low-pass loses most of its level; a 100 Hz tone through the same filter keeps most
    tone(tmp_path / "hi.wav", 3000, 200); tone(tmp_path / "lo.wav", 100, 200)
    hi = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "hi.wav", "lowpass_hz": 300}]}, str(tmp_path))[0]; lo = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "lo.wav", "lowpass_hz": 300}]}, str(tmp_path))[0]
    assert np.abs(hi[400:1200]).max() < 0.1 * 0.5 * 2 and np.abs(lo[400:1200]).max() > 0.4
    hp = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "lo.wav", "highpass_hz": 1000}]}, str(tmp_path))[0]; assert np.abs(hp[400:1200]).max() < 0.1
    # channels, pan, resampling of a 16 kHz layer, soft clip
    tone(tmp_path / "st.wav", 300, 50, ch=2); st = sfx_mix.mix({"sample_rate": 8000, "peak_db": 0, "layers": [{"file": "st.wav"}, {"file": "a.wav", "pan": -1}]}, str(tmp_path))[0]
    assert st.shape[1] == 2 and np.abs(st[:400, 1]).max() < 0.5 + 1e-3 + 0.01 and np.abs(st[:400, 0]).max() > 0.9
    assert sfx_mix.mix({"sample_rate": 8000, "layers": [{"file": "a.wav", "pan": 0.5}]}, str(tmp_path))[0].shape[1] == 2           # a pan on mono material means stereo output
    tone(tmp_path / "w.wav", 200, 100, sr=16000); assert sfx_mix.mix({"sample_rate": 8000, "layers": [{"file": "w.wav"}]}, str(tmp_path))[0].shape[0] == 800
    sc = sfx_mix.mix({"sample_rate": 8000, "soft_clip": True, "peak_db": 0, "layers": [{"file": "a.wav", "gain_db": 20}]}, str(tmp_path))[0]; assert np.abs(sc).max() <= 1.0 and np.abs(sc).max() > 0.7
    for bad in ({"layers": []}, {"layers": [{"gain_db": 1}]}, {"layers": [{"file": "a.wav", "gaindb": 1}]}):
        with pytest.raises(SystemExit): sfx_mix.mix(bad, str(tmp_path))
    json.dump(rec, open(tmp_path / "r.json", "w")); assert sfx_mix.main([str(tmp_path / "r.json"), "-o", str(tmp_path / "o.wav"), "--bits", "24"]) == 0 and wave.open(str(tmp_path / "o.wav")).getsampwidth() == 3
    assert sfx_mix.main([str(tmp_path / "r.json"), "--dry-run"]) == 0
    with pytest.raises(SystemExit): sfx_mix.main([str(tmp_path / "r.json")])
    (tmp_path / "broken.json").write_text("{nope")
    with pytest.raises(SystemExit): sfx_mix.main([str(tmp_path / "broken.json"), "--dry-run"])


# ---------- collider-preview
def test_collider_preview(tmp_path):
    rects = [(0, 0, 32, 16), (16, 8, 32, 32), (60, 0, 10, 10)]
    rep = collider_preview.analyze(rects, (64, 48)); assert rep["shapes"] == 3 and rep["area_px"] == 512 + 1024 + 100 and rep["overlaps"] == [[0, 1, 16 * 8]] and rep["outside"] == [2] and rep["coverage"] == pytest.approx(1636 / 3072, abs=1e-4)
    base = Image.new("RGBA", (64, 48), (0, 0, 0, 255)); im = np.array(collider_preview.draw(base, rects[:1], 2, labels=True))
    assert im.shape[:2] == (96, 128) and tuple(im[0, 0][:3]) == (255, 40, 40) and 0 < im[10, 10][0] < 255 and tuple(im[60, 100][:3]) == (0, 0, 0)         # outline, translucent fill, untouched area
    json.dump({"tile": [16, 16], "rects": [{"x": 0, "y": 0, "w": 32, "h": 16}, {"x": 16, "y": 16, "w": 16, "h": 16}]}, open(tmp_path / "c.json", "w")); assert collider_preview.load_rects(str(tmp_path / "c.json")) == [(0, 0, 32, 16), (16, 16, 16, 16)]
    json.dump({"type": "objectgroup", "objects": [{"x": 1, "y": 2, "width": 3, "height": 4}, {"x": 9, "y": 9, "point": True}]}, open(tmp_path / "o.json", "w")); assert collider_preview.load_rects(str(tmp_path / "o.json")) == [(1, 2, 3, 4)]
    json.dump({"layers": [{"type": "objectgroup", "objects": [{"x": 0, "y": 0, "width": 5, "height": 5}]}, {"type": "tilelayer"}]}, open(tmp_path / "ml.json", "w")); assert len(collider_preview.load_rects(str(tmp_path / "ml.json"))) == 1
    json.dump({"nothing": 1}, open(tmp_path / "bad.json", "w"))
    with pytest.raises(SystemExit): collider_preview.load_rects(str(tmp_path / "bad.json"))
    # end to end with tile-colliders output over a map
    m = {"type": "map", "orientation": "orthogonal", "width": 4, "height": 3, "tilewidth": 16, "tileheight": 16, "tilesets": [], "layers": [{"type": "tilelayer", "name": "g", "width": 4, "height": 3, "data": [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1]}]}
    json.dump(m, open(tmp_path / "m.json", "w")); g = tile_colliders.solid_grid(m, None); r = tile_colliders.merge(g)
    json.dump({"tile": [16, 16], "rects": [{"x": x * 16, "y": y * 16, "w": w * 16, "h": h * 16} for x, y, w, h in r]}, open(tmp_path / "tc.json", "w"))
    assert collider_preview.main([str(tmp_path / "tc.json"), "--map", str(tmp_path / "m.json"), "-o", str(tmp_path / "p.png"), "--scale", "2", "--json", str(tmp_path / "rep.json"), "--fail-on-overlap"]) == 0
    assert Image.open(tmp_path / "p.png").size == (128, 96) and json.load(open(tmp_path / "rep.json"))["shapes"] == len(r) and json.load(open(tmp_path / "rep.json"))["overlaps"] == []
    json.dump({"rects": [{"x": 0, "y": 0, "w": 20, "h": 20}, {"x": 10, "y": 10, "w": 20, "h": 20}]}, open(tmp_path / "ov.json", "w"))
    assert collider_preview.main([str(tmp_path / "ov.json"), "--size", "64x64", "-o", str(tmp_path / "q.png"), "--fail-on-overlap"]) == 1
    with pytest.raises(SystemExit): collider_preview.main([str(tmp_path / "ov.json"), "-o", str(tmp_path / "z.png")])


# ---------- onion-skin
def square_frames(n, size=16, step=3):
    out = []
    for i in range(n):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0)); im.paste(Image.new("RGBA", (4, 4), (0, 255, 0, 255)), (i * step, 6)); out.append(im)
    return out


def test_onion_skin(tmp_path):
    fr = square_frames(4); o = onion_skin.onion(fr, 1, 1, 1, bg=(0, 0, 0)); a = np.array(o)
    assert tuple(a[8, 4 + 1][:3]) == (0, 255, 0)                                                      # current frame (x 3..6) on top, untinted
    prev_only = a[8, 0:2]; assert prev_only[0][0] > prev_only[0][2] and prev_only[0][0] > 40            # previous frame (x 0..3) tinted red
    nxt = a[8, 7:9]; assert nxt[0][2] > nxt[0][0] and nxt[0][2] > 40                                   # next frame (x 6..9) tinted blue
    assert tuple(a[8, 14][:3]) == (0, 0, 0)                                                            # rest is background
    first = np.array(onion_skin.onion(fr, 0, 1, 1, loop=False, bg=(0, 0, 0))); assert first[8, 0][2] == 0 or first[8, 0][1] == 255            # no previous frame without --loop
    wrapped = np.array(onion_skin.onion(fr, 0, 1, 1, loop=True, bg=(0, 0, 0))); assert tuple(wrapped[8, 10][:3])[0] > 40                       # last frame ghosts before the first when looping (x 9..12, red)
    deeper = np.array(onion_skin.onion(fr, 2, 2, 0, bg=(0, 0, 0))); assert deeper[8, 0][0] > 0 and deeper[8, 0][0] < deeper[8, 4][0]            # the older ghost is fainter than the nearer one
    slow = square_frames(4, step=1); ch = onion_skin.changes(slow); assert [c["flag"] for c in ch] == ["", "", ""] and all(0 < c["changed"] < 1 for c in ch)
    noisy = [Image.fromarray(np.clip(np.array(f).astype(int) + (5 if i % 2 else 0), 0, 255).astype(np.uint8)) for i, f in enumerate([fr[1], fr[1]])]; assert onion_skin.changes(noisy)[0]["flag"] == "DUPLICATE" and onion_skin.changes(noisy, tolerance=2)[0]["flag"] != "DUPLICATE"
    dup = fr + [fr[-1]]; assert onion_skin.changes(dup)[-1]["flag"] == "DUPLICATE"
    pop = [fr[0], Image.new("RGBA", (16, 16), (255, 0, 0, 255))]; assert onion_skin.changes(pop)[0]["flag"] == "POP"
    assert len(onion_skin.changes(fr, loop=True)) == 4 and onion_skin.changes(fr, loop=True)[-1]["to"] == 0
    d = tmp_path / "f"; d.mkdir()
    for i, f in enumerate(fr): f.save(d / f"walk{i + 1}.png")
    fr[1].save(d / "walk10.png")                                                                        # natural order: walk2 < walk10
    assert [os.path.basename(p) for p in sorted((str(d / n) for n in os.listdir(d)), key=onion_skin.natural)][-1] == "walk10.png"
    assert onion_skin.main([str(d), "-o", str(tmp_path / "o.png"), "--cols", "3", "--gif", str(tmp_path / "o.gif"), "--scale", "2"]) == 0
    assert Image.open(tmp_path / "o.png").size == (3 * 32, 2 * 32) and Image.open(tmp_path / "o.gif").n_frames >= 2
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0)); sheet.paste(fr[0].crop((0, 0, 16, 16)), (0, 0)); sheet.paste(fr[2].crop((0, 0, 16, 16)), (16, 0)); sheet.save(tmp_path / "sheet.png")
    assert onion_skin.main([str(tmp_path / "sheet.png"), "-o", str(tmp_path / "s.png"), "--grid", "16x16"]) == 0 and Image.open(tmp_path / "s.png").size == (32, 16)
    fr[0].save(tmp_path / "a.gif", save_all=True, append_images=fr[1:], duration=100, loop=0); assert len(onion_skin.load_frames(str(tmp_path / "a.gif"))) == 4
    mixed = tmp_path / "mixed"; mixed.mkdir(); Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(mixed / "a.png"); Image.new("RGBA", (12, 10), (0, 0, 255, 255)).save(mixed / "b.png")
    ms = onion_skin.load_frames(str(mixed)); assert ms[0].size == ms[1].size == (12, 10) and ms[0].getpixel((6, 9))[3] == 255 and ms[0].getpixel((0, 0))[3] == 0       # unequal frames are bottom-centre aligned
    (tmp_path / "emptydir").mkdir()
    with pytest.raises(SystemExit): onion_skin.load_frames(str(tmp_path / "emptydir"))
