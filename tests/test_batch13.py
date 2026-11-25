import csv, json, math, os, wave
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageFont
import hitbox_gen, audio_concat, wav_split_silence, map_clean, nine_slice, font_preview, parallax_preview, tile_anim_gif
import audio_tidy, tilemap_stats


# ---------- hitbox-gen
def blob(w=16, h=16, box=(4, 2, 12, 10), color=(255, 0, 0, 255)):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); im.paste(Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), color), box[:2]); return im


def test_hitbox_shapes():
    s = hitbox_gen.shapes(blob())
    assert s["aabb"] == {"x": 4, "y": 2, "w": 8, "h": 8} and s["empty"] is False
    # box is 8x8, centre 8,6; farthest opaque corners of the box are 0.5 px in from 4,2 and 12,10
    assert s["circle"]["cx"] == 8 and s["circle"]["cy"] == 6 and s["circle"]["r"] == pytest.approx(math.hypot(3.5, 3.5), abs=0.01)
    assert s["capsule"]["axis"] == "y" or s["capsule"]["length"] == 0                                    # square: either axis, zero shaft
    assert s["capsule"]["length"] == pytest.approx(0, abs=1e-6) and s["capsule"]["r"] == pytest.approx(4, abs=1e-6)
    tall = hitbox_gen.shapes(blob(box=(6, 1, 10, 15))); assert tall["capsule"]["axis"] == "y" and tall["capsule"]["length"] == pytest.approx(10, abs=1e-6) and tall["capsule"]["r"] == pytest.approx(2, abs=1e-6)
    wide = hitbox_gen.shapes(blob(box=(1, 6, 15, 10))); assert wide["capsule"]["axis"] == "x" and wide["capsule"]["length"] == pytest.approx(10, abs=1e-6)
    padded = hitbox_gen.shapes(blob(), pad=2); assert padded["aabb"] == {"x": 2, "y": 0, "w": 12, "h": 12} and padded["circle"]["r"] == pytest.approx(s["circle"]["r"] + 2, abs=0.01)
    empty = hitbox_gen.shapes(Image.new("RGBA", (8, 8), (0, 0, 0, 0))); assert empty["empty"] and empty["circle"] is None and empty["aabb"]["w"] == 0
    # centroid of an L is not the bbox centre
    L = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); L.paste(Image.new("RGBA", (6, 2), (255, 255, 255, 255)), (0, 0)); L.paste(Image.new("RGBA", (2, 6), (255, 255, 255, 255)), (0, 2))
    c0, c1 = hitbox_gen.shapes(L), hitbox_gen.shapes(L, centroid=True)
    assert (c0["circle"]["cx"], c0["circle"]["cy"]) != (pytest.approx(c1["circle"]["cx"]), pytest.approx(c1["circle"]["cy"])) or c1["circle"]["cx"] < c0["circle"]["cx"]
    assert c1["circle"]["cx"] < c0["circle"]["cx"] and c1["circle"]["cy"] < c0["circle"]["cy"]
    n = hitbox_gen.normalize(s); assert n["aabb"]["x"] == 4 / 16 and n["aabb"]["w"] == 8 / 16 and n["circle"]["cx"] == 0.5


def test_hitbox_cli(tmp_path):
    blob().save(tmp_path / "a.png"); blob(box=(2, 2, 6, 14)).save(tmp_path / "b.png")
    assert hitbox_gen.main([str(tmp_path), "-o", str(tmp_path / "h.json"), "--pad", "1"]) == 0
    fr = json.load(open(tmp_path / "h.json"))["frames"]; assert "a" in fr and "b" in fr and fr["b"]["capsule"]["axis"] == "y"
    sheet = Image.new("RGBA", (32, 16), (0, 0, 0, 0)); sheet.paste(blob(), (0, 0)); sheet.paste(blob(), (16, 0)); sheet.save(tmp_path / "s.png")
    assert hitbox_gen.main([str(tmp_path / "s.png"), "--grid", "16x16", "-o", str(tmp_path / "g.json")]) == 0 and len(json.load(open(tmp_path / "g.json"))["frames"]) == 2
    # atlas with a trimmed frame: the reconstructed canvas (sourceSize) is the coordinate space
    atlas = {"frames": {"r": {"frame": {"x": 1, "y": 1, "w": 6, "h": 6}, "spriteSourceSize": {"x": 2, "y": 2, "w": 6, "h": 6}, "sourceSize": {"w": 10, "h": 10}}}, "meta": {"image": "s.png"}}
    # build a tiny atlas image
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); im.paste(Image.new("RGBA", (6, 6), (0, 255, 0, 255)), (1, 1)); im.save(tmp_path / "atl.png")
    atlas["meta"]["image"] = "atl.png"; json.dump(atlas, open(tmp_path / "atl.json", "w"))
    assert hitbox_gen.main(["--atlas", str(tmp_path / "atl.json"), "-o", str(tmp_path / "t.json")]) == 0
    aabb = json.load(open(tmp_path / "t.json"))["frames"]["r"]["aabb"]; assert aabb == {"x": 2, "y": 2, "w": 6, "h": 6}
    with pytest.raises(SystemExit): hitbox_gen.main(["-o", str(tmp_path / "x.json")])


# ---------- audio-concat
def tone(n, amp=0.4, sr=8000, ch=1, f=220):
    t = np.arange(n) / sr; return (amp * np.sin(2 * np.pi * f * t))[:, None] * np.ones((1, ch))


def test_audio_concat(tmp_path):
    audio_tidy.write_wav(str(tmp_path / "a.wav"), tone(800), 8000, 16)
    audio_tidy.write_wav(str(tmp_path / "b.wav"), tone(1600, ch=2, f=440), 16000, 16)                     # different rate and channel count
    y, sr, cues, info = audio_concat.concat([str(tmp_path / "a.wav"), str(tmp_path / "b.wav")], gap_ms=100, peak_db=0)
    assert sr == 8000 and y.shape[1] == 2 and cues[0]["duration_s"] == 0.1
    # a is 800 samples @ 8k = 0.1s, then 100 ms gap, then b resampled 1600@16k -> 800@8k = 0.1s
    assert cues[1]["start_s"] == pytest.approx(0.2, abs=0.002) and info["duration_s"] == pytest.approx(0.3, abs=0.002)
    assert np.abs(y[int(0.12 * sr):int(0.18 * sr)]).max() < 1e-6                                         # the gap is silent
    assert np.abs(y[:800]).max() > 0.3 and np.abs(y[-800:]).max() > 0.1
    # peak cap: two full-scale files added after a slate would clip without scaling... a single file at 0.4 stays unscaled
    assert info["scale_db"] == 0.0
    loud, _, _, inf = audio_concat.concat([str(tmp_path / "a.wav")], peak_db=-6.0)
    # 0.4 peak is already under -6 dBFS (~0.5), so still unscaled
    assert inf["scale_db"] == 0.0
    audio_tidy.write_wav(str(tmp_path / "l.wav"), tone(800, amp=0.9), 8000)
    _, _, _, inf2 = audio_concat.concat([str(tmp_path / "l.wav")], peak_db=-6.0); assert inf2["scale_db"] < 0
    y2, sr2, cues2, _ = audio_concat.concat([str(tmp_path / "a.wav"), str(tmp_path / "a.wav")], slate_ms=50, gap_ms=0)
    assert cues2[0]["start_s"] == pytest.approx(0.09, abs=0.005)                                        # 50 ms silence + 40 ms beep
    assert audio_concat.main([str(tmp_path / "a.wav"), str(tmp_path / "b.wav"), "-o", str(tmp_path / "out.wav"), "--gap-ms", "50", "--cues-json", str(tmp_path / "c.json"), "--bits", "24"]) == 0
    assert wave.open(str(tmp_path / "out.wav")).getsampwidth() == 3 and json.load(open(tmp_path / "c.json"))[1]["start_s"] > 0
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit): audio_concat.collect([str(tmp_path / "empty")])


# ---------- wav-split-silence
def test_wav_split_silence(tmp_path):
    sr = 8000
    # 0.1s tone, 0.4s silence, 0.15s tone, 0.05s short silence (should NOT split), 0.1s tone, 0.4s silence, 0.02s blip (dropped by min-keep)
    parts = [tone(int(0.1 * sr)), np.zeros((int(0.4 * sr), 1)), tone(int(0.15 * sr), f=330), np.zeros((int(0.05 * sr), 1)), tone(int(0.1 * sr), f=330), np.zeros((int(0.4 * sr), 1)), tone(int(0.02 * sr))]
    audio_tidy.write_wav(str(tmp_path / "t.wav"), np.concatenate(parts), sr, 24)
    cuts = wav_split_silence.regions(np.concatenate(parts), sr, thresh_db=-40, min_silence_ms=200, min_keep_ms=50, pad_ms=0)
    assert len(cuts) == 2
    # first region is the first tone; second is the mid pair joined across the 50 ms dip
    assert (cuts[0][1] - cuts[0][0]) / sr == pytest.approx(0.1, abs=0.02)
    assert (cuts[1][1] - cuts[1][0]) / sr == pytest.approx(0.30, abs=0.04)
    assert wav_split_silence.main([str(tmp_path / "t.wav"), "-o", str(tmp_path / "out"), "--min-silence-ms", "200", "--min-keep-ms", "50", "--pad-ms", "0", "--json", str(tmp_path / "c.json")]) == 0
    files = sorted(os.listdir(tmp_path / "out")); assert "take_0001.wav" in files and "take_0002.wav" in files and "take_0003.wav" not in files
    assert wave.open(str(tmp_path / "out" / "take_0001.wav")).getsampwidth() == 3
    assert len(json.load(open(tmp_path / "c.json"))) == 2
    audio_tidy.write_wav(str(tmp_path / "quiet.wav"), np.zeros((sr, 1)), sr)
    with pytest.raises(SystemExit): wav_split_silence.main([str(tmp_path / "quiet.wav"), "-o", str(tmp_path / "q")])


# ---------- map-clean
def test_map_clean(tmp_path):
    m = {"type": "map", "width": 3, "height": 1, "tilewidth": 16, "tileheight": 16, "properties": [],
         "tilesets": [{"name": "used", "firstgid": 1, "tilecount": 10}, {"name": "spare", "firstgid": 20, "tilecount": 5}],
         "layers": [
             {"type": "tilelayer", "name": "ground", "width": 3, "height": 1, "data": [1, 2, 0], "properties": []},
             {"type": "tilelayer", "name": "fog", "width": 3, "height": 1, "data": [0, 0, 0], "visible": False},
             {"type": "group", "name": "fx", "layers": [{"type": "objectgroup", "name": "empty_objs", "objects": []},
                                                       {"type": "objectgroup", "name": "mobs", "objects": [{"id": 1, "type": "enemy"}]}]},
             {"type": "tilelayer", "name": "hidden_full", "width": 3, "height": 1, "data": [1, 1, 1], "visible": False},
         ]}
    c, r = map_clean.clean(m)
    names = [l["name"] for l in c["layers"]]
    assert names == ["ground", "fx"] and [l["name"] for l in c["layers"][1]["layers"]] == ["mobs"]
    assert r["hidden_layers"] == ["fog", "hidden_full"] and "empty_objs" in r["empty_layers"] and r["unused_tilesets"] == ["spare"]
    assert [t["name"] for t in c["tilesets"]] == ["used"] and "properties" not in c and "properties" not in c["layers"][0]
    # keep flags
    c2, r2 = map_clean.clean(m, drop_hidden=False, drop_empty=False, drop_unused_tilesets=False, drop_empty_properties=False)
    assert len(c2["layers"]) == 4 and len(c2["tilesets"]) == 2 and "properties" in c2
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert map_clean.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "c.json"), "--pretty"]) == 0
    out = json.load(open(tmp_path / "c.json")); assert "spare" not in json.dumps(out) and out["layers"][0]["data"] == [1, 2, 0]
    with pytest.raises(SystemExit): map_clean.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "m.json")])
    # infinite chunks: an empty chunked layer is dropped, a used tileset is kept
    inf = {"type": "map", "infinite": True, "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4}],
           "layers": [{"type": "tilelayer", "name": "g", "chunks": [{"x": 0, "y": 0, "width": 2, "height": 1, "data": [1, 0]}]},
                      {"type": "tilelayer", "name": "z", "chunks": [{"x": 0, "y": 0, "width": 2, "height": 1, "data": [0, 0]}]}]}
    c3, r3 = map_clean.clean(inf); assert [l["name"] for l in c3["layers"]] == ["g"] and r3["empty_layers"] == ["z"]


# ---------- nine-slice
def panel():
    """8x8 panel: unique colours in each of the 9 regions with insets 2,2,2,2 (centre is 4x4)."""
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 255)); cols = {
        (0, 0, 2, 2): (255, 0, 0, 255), (2, 0, 6, 2): (0, 255, 0, 255), (6, 0, 8, 2): (0, 0, 255, 255),
        (0, 2, 2, 6): (255, 255, 0, 255), (2, 2, 6, 6): (255, 255, 255, 255), (6, 2, 8, 6): (255, 0, 255, 255),
        (0, 6, 8, 8): (0, 255, 255, 255),
    }
    # fix sw/s/se properly
    im.paste(Image.new("RGBA", (2, 2), (0, 128, 128, 255)), (0, 6))
    im.paste(Image.new("RGBA", (4, 2), (128, 0, 128, 255)), (2, 6))
    im.paste(Image.new("RGBA", (2, 2), (128, 128, 0, 255)), (6, 6))
    im.paste(Image.new("RGBA", (2, 2), (255, 0, 0, 255)), (0, 0))
    im.paste(Image.new("RGBA", (4, 2), (0, 255, 0, 255)), (2, 0))
    im.paste(Image.new("RGBA", (2, 2), (0, 0, 255, 255)), (6, 0))
    im.paste(Image.new("RGBA", (2, 4), (255, 255, 0, 255)), (0, 2))
    im.paste(Image.new("RGBA", (4, 4), (255, 255, 255, 255)), (2, 2))
    im.paste(Image.new("RGBA", (2, 4), (255, 0, 255, 255)), (6, 2))
    return im


def test_nine_slice(tmp_path):
    im = panel(); L, T, R, B = nine_slice.insets_of(8, 8, insets=(2, 2, 2, 2)); assert (L, T, R, B) == (2, 2, 2, 2)
    assert nine_slice.insets_of(8, 8, center=(2, 2, 4, 4)) == (2, 2, 2, 2)
    with pytest.raises(SystemExit): nine_slice.insets_of(8, 8, insets=(5, 2, 5, 2))
    out = nine_slice.stretch(im, 2, 2, 2, 2, 16, 12, nearest=True)
    assert out.size == (16, 12)
    a = np.array(out)
    # corners copied, not stretched: NW is still 2x2 red, SE is 2x2 olive
    assert (a[0:2, 0:2] == (255, 0, 0, 255)).all() and (a[10:12, 14:16] == (128, 128, 0, 255)).all()
    # centre is white and has grown
    assert (a[4:8, 4:12] == (255, 255, 255, 255)).all()
    # north edge is green and stretched horizontally
    assert (a[0:2, 2:14] == (0, 255, 0, 255)).all()
    with pytest.raises(SystemExit): nine_slice.stretch(im, 2, 2, 2, 2, 3, 12, True)
    prev = nine_slice.preview(im, 2, 2, 2, 2, [(8, 8), (16, 12)]); assert prev.width > 16 + 8 and prev.height >= 12
    im.save(tmp_path / "p.png")
    assert nine_slice.main([str(tmp_path / "p.png"), "--insets", "2,2,2,2", "--size", "16x12", "-o", str(tmp_path / "b.png"), "--preview", str(tmp_path / "pr.png"), "--json", str(tmp_path / "i.json")]) == 0
    assert Image.open(tmp_path / "b.png").size == (16, 12) and json.load(open(tmp_path / "i.json"))["min_size"] == [4, 4]
    with pytest.raises(SystemExit): nine_slice.main([str(tmp_path / "p.png"), "--insets", "2,2,2,2"])


# ---------- font-preview
def test_font_preview(tmp_path):
    # default font can draw ASCII and cannot draw a CJK character or often é - we assert the mechanism with a private-use char
    font = ImageFont.load_default(16)
    assert font_preview.missing_chars(font, "ABC 123") == []
    assert font_preview.missing_chars(font, "A\u4e00B") == []   # default font draws a tofu; without a cmap we cannot tell
    assert "\u4e00" in font_preview.missing_chars(font, "A\u4e00B", cmap={ord("A"), ord("B")}) and "A" not in font_preview.missing_chars(font, "A\u4e00B", cmap={ord("A"), ord("B")})
    (tmp_path / "s.csv").write_text("id,en,ja\nhi,Hello,\u4e00\u4e8c\n", encoding="utf-8")
    chars = font_preview.unique_from_csv(str(tmp_path / "s.csv")); assert "H" in chars and "\u4e00" in chars
    im, miss = font_preview.render_sheet(None, [16, 24], ["Hello", "\u4e00"]); assert im.size[0] > 20 and im.size[1] > 20 and miss == []   # no cmap on the default font
    assert font_preview.main(["default", "-o", str(tmp_path / "q.png"), "--sizes", "16", "--no-pangram", "--text", "ABC"]) == 0
    deja = str(Path(__file__).resolve().parent / "fixtures" / "DejaVuSans-subset.ttf")
    assert os.path.isfile(deja)
    im, miss = font_preview.render_sheet(deja, [16], ["Hello", "\u4e00"]); assert "\u4e00" in miss and "H" not in miss
    assert font_preview.main([deja, "-o", str(tmp_path / "p.png"), "--sizes", "16,20", "--text", "Hello", "--csv", str(tmp_path / "s.csv"), "--json", str(tmp_path / "m.json")]) == 1
    assert Image.open(tmp_path / "p.png").size[1] > 20 and "\u4e00" in json.load(open(tmp_path / "m.json"))["missing"]
    assert font_preview.main([deja, "-o", str(tmp_path / "d.png"), "--sizes", "18", "--no-pangram", "--text", "Hello 123"]) == 0
    assert font_preview.cmap_codepoints(None) is None and ord("A") in font_preview.cmap_codepoints(deja) and 0x4E00 not in font_preview.cmap_codepoints(deja)


# ---------- parallax-preview
def test_parallax(tmp_path):
    # a 16x8 red/blue striped layer (2-px columns) and a 8x8 green sprite-like layer
    a = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    for x in range(16):
        c = (255, 0, 0, 255) if (x // 2) % 2 == 0 else (0, 0, 255, 255); Image.Image.paste(a, Image.new("RGBA", (1, 8), c), (x, 0))
    b = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); b.paste(Image.new("RGBA", (4, 4), (0, 255, 0, 255)), (0, 2))
    a.save(tmp_path / "a.png"); b.save(tmp_path / "b.png")
    # with speed 0 the first frame and a later frame of that layer stay put; with speed 1 the layer shifts by travel/frames
    frames = parallax_preview.render([(a, 0.0, 0.0)], 8, 8, frames=4, travel_x=8)
    assert frames[0].size == (8, 8) and np.array_equal(np.array(frames[0]), np.array(frames[3]))
    moved = parallax_preview.render([(a, 1.0, 0.0)], 8, 8, frames=2, travel_x=2)
    # frame 0 at cam=0, frame 1 at cam=1 (travel 2 over 2 frames: t=i/2, wait t=i/frames so i=1 -> 1 px)
    # travel_x * (i/frames): i=1, frames=2 -> 1 px. Stripe width 2, so a 1 px shift is visible
    assert not np.array_equal(np.array(moved[0]), np.array(moved[1]))
    # wrapping: travel of exactly one layer width with speed 1, last frame should match first... t = i/frames, i never reaches frames, so last is not a full wrap.
    # speed 1, travel = width, frames = width: frame i is shifted by i px; we can compare frame 0 with a wrap of the source
    assert parallax_preview.parse_speeds("0,0.5,1", 3) == [(0, 0), (0.5, 0), (1, 0)]
    assert parallax_preview.parse_speeds("0.2:0.1,1", 2) == [(0.2, 0.1), (1.0, 0.0)]
    with pytest.raises(SystemExit): parallax_preview.parse_speeds("1", 2)
    assert parallax_preview.main([str(tmp_path / "a.png"), str(tmp_path / "b.png"), "-o", str(tmp_path / "p.gif"), "--speeds", "0.25,1", "--width", "8", "--height", "8", "--frames", "6", "--fps", "8", "--png", str(tmp_path / "p.png")]) == 0
    g = Image.open(tmp_path / "p.gif"); assert g.size == (8, 8) and g.n_frames == 6 and Image.open(tmp_path / "p.png").size == (8, 8)


# ---------- tile-anim-gif
def test_tile_anim(tmp_path):
    # 16x16 tileset, 2 columns, 4 tiles: 0 red, 1 green, 2 blue, 3 yellow. Tile 0 animates 0,1,2 at 100ms each.
    ts = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for i, c in enumerate(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255))):
        ts.paste(Image.new("RGBA", (16, 16), c), ((i % 2) * 16, (i // 2) * 16))
    ts.save(tmp_path / "t.png")
    tileset = {"name": "t", "image": "t.png", "tilewidth": 16, "tileheight": 16, "columns": 2, "tilecount": 4, "firstgid": 1,
               "tiles": [{"id": 0, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 100}, {"tileid": 2, "duration": 100}]}]}
    json.dump(tileset, open(tmp_path / "t.json", "w"))
    m = {"type": "map", "orientation": "orthogonal", "width": 2, "height": 1, "tilewidth": 16, "tileheight": 16, "infinite": False,
         "tilesets": [tileset], "layers": [{"type": "tilelayer", "name": "g", "width": 2, "height": 1, "visible": True, "data": [1, 4]}]}  # gid 1 = tile 0 (animated), gid 4 = tile 3 (static yellow)
    json.dump(m, open(tmp_path / "m.json", "w"))
    assert tile_anim_gif.main([str(tmp_path / "t.json"), "-o", str(tmp_path / "gifs"), "--scale", "2"]) == 0
    g = Image.open(tmp_path / "gifs" / "t_0.gif"); assert g.size == (32, 32) and g.n_frames == 3
    g.seek(0); assert np.array(g.convert("RGB"))[2, 2, 0] > 200
    g.seek(1); assert np.array(g.convert("RGB"))[2, 2, 1] > 200
    # map preview: the right cell stays yellow, the left cell cycles
    assert tile_anim_gif.main([str(tmp_path / "m.json"), "-o", str(tmp_path / "mapout"), "--tick-ms", "100", "--duration-ms", "300", "--scale", "1"]) == 0
    mg = Image.open(tmp_path / "mapout" / "map.gif"); assert mg.size == (32, 16) and mg.n_frames == 3
    mg.seek(0); a = np.array(mg.convert("RGB")); assert a[8, 8, 0] > 200 and a[8, 24, 0] > 200 and a[8, 24, 1] > 200          # left red, right yellow
    mg.seek(2); a = np.array(mg.convert("RGB")); assert a[8, 8, 2] > 200 and a[8, 24, 0] > 200 and a[8, 24, 1] > 200          # left blue, right still yellow
    # remap keeps flip flags
    flipped = dict(m); flipped["layers"] = [{"type": "tilelayer", "name": "g", "width": 2, "height": 1, "data": [1 | 0x80000000, 4]}]
    mm = tile_anim_gif.remap_map(flipped, [( {"firstgid": 1}, {0: [(0, 100), (1, 100), (2, 100)]} )], 150)
    assert mm["layers"][0]["data"][0] & 0x80000000 and (mm["layers"][0]["data"][0] & 0x1FFFFFFF) == 2                      # mid-cycle = tileid 1, gid 2, plus H flag
    # no animations -> exit 1 when not a map? tileset with no anim
    json.dump({"name": "t", "image": "t.png", "tilewidth": 16, "tileheight": 16, "columns": 2, "tiles": []}, open(tmp_path / "empty.json", "w"))
    assert tile_anim_gif.main([str(tmp_path / "empty.json"), "-o", str(tmp_path / "e")]) == 1
