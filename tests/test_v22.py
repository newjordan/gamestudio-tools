"""Version 2.2.0 gap-closing tests (self-contained: no samples/ dependency)."""
import json, os, re, subprocess

import pytest
from PIL import Image

import map_objects_to_godot
from gst_errors import GstInputError
from test_batch31 import godot_bin, _isolate
from test_v21 import (FD, FH, FV, have_render, quad_tile, render_frame, tiled_xform)


# ---------------------------------------------------------------- map-objects: TSX, collections, animation
def tsx_project(tmp_path, anim=True):
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    sheet = Image.new("RGBA", (32, 16), (90, 90, 90, 255))
    sheet.paste(quad_tile(), (0, 0))
    sheet.save(proj / "tiles.png")
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(proj / "red.png")
    Image.new("RGBA", (16, 8), (0, 0, 255, 255)).save(proj / "blue.png")
    animation = ('<animation><frame tileid="0" duration="60000"/><frame tileid="1" duration="100"/></animation>'
                 if anim else "")
    (proj / "atlas.tsx").write_text(
        '<?xml version="1.0"?>\n<tileset version="1.10" name="atlas" tilewidth="16" tileheight="16" tilecount="2" columns="2">\n'
        ' <tileoffset x="0" y="0"/>\n <image source="tiles.png" width="32" height="16"/>\n'
        ' <tile id="0">%s</tile>\n</tileset>\n' % animation)
    (proj / "coll.tsx").write_text(
        '<?xml version="1.0"?>\n<tileset version="1.10" name="coll" tilewidth="16" tileheight="8" tilecount="2" columns="0" '
        'objectalignment="topleft">\n <tile id="0"><image source="red.png" width="8" height="8"/></tile>\n'
        ' <tile id="1"><image source="blue.png" width="16" height="8"/></tile>\n</tileset>\n')
    doc = {"type": "map", "orientation": "orthogonal", "width": 8, "height": 4, "tilewidth": 16, "tileheight": 16,
           "tilesets": [{"firstgid": 1, "source": "atlas.tsx"}, {"firstgid": 10, "source": "coll.tsx"}],
           "layers": [{"type": "objectgroup", "name": "o", "objects": [
               {"id": 1, "name": "anim", "gid": 1, "x": 0, "y": 32, "width": 16, "height": 16},
               {"id": 2, "name": "animflip", "gid": 1 | FD | FH, "x": 24, "y": 32, "width": 16, "height": 16},
               {"id": 3, "name": "red", "gid": 10, "x": 48, "y": 0},
               {"id": 4, "name": "blue", "gid": 11, "x": 64, "y": 0},
               {"id": 5, "name": "plain", "gid": 2, "x": 96, "y": 32, "width": 16, "height": 16}]}]}
    src = proj / "m.json"
    src.write_text(json.dumps(doc))
    return src, proj


def test_map_objects_external_tsx_collection_and_animation(tmp_path):
    src, proj = tsx_project(tmp_path)
    out = tmp_path / "o.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["sprites"] == 5 and rec["animated_sprites"] == 2 and rec["unknown_gids"] == 0
    assert set(rec["textures"]) == {"res://tiles.png", "res://red.png", "res://blue.png"}
    text = out.read_text()
    assert text.count('type="AnimatedSprite2D"') == 2 and text.count('type="Sprite2D"') == 3
    assert text.count('type="SpriteFrames"') == 1           # both objects share one animation resource
    assert text.count('type="AtlasTexture"') == 2
    assert '"speed": 10 }]' in text and '"duration": 600,' in text and '"duration": 1,' in text
    assert 'autoplay = "default"' in text
    # collection tiles keep their own image sizes; topleft alignment puts the origin at the object's (x, y)
    assert "region_rect = Rect2(0, 0, 8, 8)" in text and "region_rect = Rect2(0, 0, 16, 8)" in text
    assert "position = Vector2(48, 0)" in text and "position = Vector2(64, 0)" in text
    # --no-animation: plain Sprite2D showing the first frame
    assert map_objects_to_godot.main([str(src), "-o", str(tmp_path / "s.tscn"), "--no-animation"]) == 0
    assert "AnimatedSprite2D" not in (tmp_path / "s.tscn").read_text()


def test_map_objects_inline_json_collection_and_missing_tsx(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    Image.new("RGBA", (4, 6), (1, 2, 3, 255)).save(proj / "one.png")
    doc = {"type": "map", "orientation": "orthogonal", "width": 2, "height": 2, "tilewidth": 8, "tileheight": 8,
           "tilesets": [{"firstgid": 1, "name": "c", "tilewidth": 8, "tileheight": 8, "tilecount": 1, "columns": 0,
                         "tiles": [{"id": 0, "image": "one.png", "imagewidth": 4, "imageheight": 6}]}],
           "layers": [{"type": "objectgroup", "name": "o", "objects": [{"id": 1, "gid": 1, "x": 0, "y": 8}]}]}
    src = tmp_path / "c.json"
    src.write_text(json.dumps(doc))
    assert map_objects_to_godot.main([str(src), "-o", str(tmp_path / "c.tscn")]) == 0
    assert "region_rect = Rect2(0, 0, 4, 6)" in (tmp_path / "c.tscn").read_text()
    doc["tilesets"] = [{"firstgid": 1, "source": "nowhere.tsx"}]
    src.write_text(json.dumps(doc))
    with pytest.raises(GstInputError):
        map_objects_to_godot.main([str(src), "-o", str(tmp_path / "bad.tscn")])
    (tmp_path / "bad.tsx").write_text('<tileset tilewidth="x" tileheight="8"><image source="a.png"/></tileset>')
    doc["tilesets"] = [{"firstgid": 1, "source": "bad.tsx"}]
    src.write_text(json.dumps(doc))
    with pytest.raises(GstInputError):
        map_objects_to_godot.main([str(src), "-o", str(tmp_path / "bad.tscn")])


@pytest.mark.skipif(not have_render(), reason="needs GODOT_BIN and xvfb-run for a software-GL render")
def test_map_objects_animated_and_collection_render_in_godot(tmp_path):
    src, proj = tsx_project(tmp_path)
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "main.tscn")]) == 0
    got = render_frame(tmp_path, proj, 128, 64)
    exp = Image.new("RGBA", (128, 64), (0, 0, 0, 255))
    tile = quad_tile()
    exp.paste(tile, (0, 16))                                                # animated, first frame is the quad tile
    exp.paste(tiled_xform(tile, 1 | FD | FH), (24, 16))                     # same animation with diagonal + H flip
    exp.paste(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), (48, 0))         # collection tile images
    exp.paste(Image.new("RGBA", (16, 8), (0, 0, 255, 255)), (64, 0))
    exp.paste(Image.new("RGBA", (16, 16), (90, 90, 90, 255)), (96, 16))     # plain sprite of tile 1
    exp = exp.convert("RGB")
    bad = [(x, y) for y in range(64) for x in range(128) if got.getpixel((x, y)) != exp.getpixel((x, y))]
    assert not bad, "%d pixels differ, first %s" % (len(bad), bad[:5])


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_map_objects_animation_resources_in_godot(tmp_path):
    src, proj = tsx_project(tmp_path)
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "main.tscn")]) == 0
    (proj / "project.godot").write_text("config_version=5\n\n[application]\n\nconfig/name=\"gst-anim\"\n")
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var root = load("res://main.tscn").instantiate()\n'
        '	var a: AnimatedSprite2D = root.get_node("o/animflip")\n'
        '	var sf: SpriteFrames = a.sprite_frames\n'
        '	print("ANIM frames=", sf.get_frame_count("default"), " speed=", sf.get_animation_speed("default"),'
        ' " loop=", sf.get_animation_loop("default"), " d0=", sf.get_frame_duration("default", 0),'
        ' " d1=", sf.get_frame_duration("default", 1), " autoplay=", a.autoplay, " flip_h=", a.flip_h)\n'
        '	print("SIZE ", sf.get_frame_texture("default", 0).get_size(), " ", root.get_node("o/blue").texture.get_size())\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"], env=env, capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    assert "ANIM frames=2 speed=10.0 loop=true d0=600.0 d1=1.0 autoplay=default flip_h=false" in r.stdout, r.stdout
    assert "SIZE (16.0, 16.0) (16.0, 8.0)" in r.stdout, r.stdout


# ---------------------------------------------------------------- ase-json-import shares the tag expansion
def _ase_sheet(tags, n=5):
    frames = [{"filename": "f%d" % i, "frame": {"x": i * 8, "y": 0, "w": 8, "h": 8}, "duration": 100 + i * 10} for i in range(n)]
    return {"frames": frames, "meta": {"image": "s.png", "size": {"w": n * 8, "h": 8}, "frameTags": tags}}


def test_ase_json_import_uses_shared_expansion_and_repeat():
    import ase_json_import, ase_tags, ase_to_godot
    assert ase_to_godot.expand_tag is ase_tags.expand_tag and ase_json_import.expand_tag is ase_tags.expand_tag
    tags = [{"name": "f", "from": 1, "to": 3, "direction": "forward"},
            {"name": "r", "from": 1, "to": 3, "direction": "reverse"},
            {"name": "pp", "from": 0, "to": 3, "direction": "pingpong"},
            {"name": "ppr", "from": 0, "to": 3, "direction": "pingpong_reverse"},
            {"name": "pp2", "from": 0, "to": 1, "direction": "pingpong"},
            {"name": "x2", "from": 0, "to": 2, "direction": "pingpong", "repeat": "2"},
            {"name": "fx3", "from": 1, "to": 2, "repeat": 3}]
    _, clips, _ = ase_json_import.convert(_ase_sheet(tags), once={"f"})
    names = lambda c: [int(n[1:]) for n in clips[c]["frames"]]
    assert names("f") == [1, 2, 3] and clips["f"]["loop"] is False                 # --once still wins
    assert names("r") == [3, 2, 1] and clips["r"]["direction"] == "reverse" and clips["r"]["loop"] is True
    assert names("pp") == [0, 1, 2, 3, 2, 1] and names("ppr") == [3, 2, 1, 0, 1, 2]
    assert names("pp2") == [0, 1] and clips["pp2"]["loop"] is True
    assert names("x2") == [0, 1, 2, 1, 0, 1, 2, 1, 0] and clips["x2"]["loop"] is False      # two cycles, ends on its start
    assert names("fx3") == [1, 2, 1, 2, 1, 2] and clips["fx3"]["loop"] is False
    assert clips["pp"]["durations_ms"] == [100, 110, 120, 130, 120, 110]
    # the same tag expands identically through ase-to-godot's clip builder
    durs = [100 + i * 10 for i in range(5)]
    god = ase_to_godot.clips_from_doc(5, durs, [dict(t) for t in tags])
    for t in tags:
        got = god[t["name"]]["frames"] if isinstance(god, dict) and t["name"] in god else god[0][t["name"]]["frames"]
        if t["name"] != "f":
            assert [int(n.split("_")[1].split(".")[0]) for n in got] == names(t["name"]), t["name"]
    _, plain, _ = ase_json_import.convert(_ase_sheet(tags), directions=False)
    assert all(c["direction"] == "forward" and c["loop"] for c in plain.values())
    assert [int(n[1:]) for n in plain["pp"]["frames"]] == [0, 1, 2, 3]


def test_ase_json_import_typed_errors(tmp_path):
    import ase_json_import
    for bad in ({}, [], {"frames": 5}, {"frames": [1]}, {"frames": [{"frame": {}}]},
                {"frames": [{"frame": {"x": 0, "y": 0, "w": 1, "h": 1}, "duration": "slow"}]},
                _ase_sheet([{"name": "t", "from": "a", "to": 1}]), _ase_sheet([{"name": "t", "from": 3, "to": 1}]),
                _ase_sheet([{"from": 0, "to": 1}])):
        with pytest.raises(GstInputError):
            ase_json_import.convert(bad)
    src = tmp_path / "bad.json"
    src.write_text("{nope")
    with pytest.raises(GstInputError):
        ase_json_import.main([str(src), "-o", str(tmp_path / "o")])


# ---------------------------------------------------------------- font-to-godot glyph rect bounds
import font_to_godot
import test_v21


def _font(tmp_path, monkeypatch, fmt, chars, size=(16, 16)):
    monkeypatch.setattr(test_v21, "FONT_CHARS", chars)
    Image.new("RGBA", size, (255, 255, 255, 255)).save(tmp_path / "label.png")
    maker = {"text": test_v21.bmfont_text, "xml": test_v21.bmfont_xml, "binary": test_v21.bmfont_binary}[fmt]
    src = tmp_path / "label.fnt"
    src.write_bytes(maker())
    return src


@pytest.mark.parametrize("fmt", ["text", "xml", "binary"])
def test_font_glyph_rects_inside_page_are_accepted(tmp_path, monkeypatch, fmt):
    ok = [(65, 0, 0, 8, 8, 0, 0, 8), (66, 8, 8, 8, 8, 0, 0, 8),       # touches the right and bottom edge exactly
          (32, 0, 0, 0, 0, 0, 0, 4)]                                   # a space: zero size
    src = _font(tmp_path, monkeypatch, fmt, ok)
    assert font_to_godot.main([str(src), "-o", str(tmp_path / "t.tres"), "--json", str(tmp_path / "r.json")]) == 0
    assert json.load(open(tmp_path / "r.json"))["page_sizes"] == {"label.png": [16, 16]}


@pytest.mark.parametrize("fmt", ["text", "xml", "binary"])
@pytest.mark.parametrize("chars,needle", [
    ([(65, 12, 0, 8, 8, 0, 0, 8)], "glyph id 65 rectangle x=12 y=0 width=8 height=8 lies outside the 16x16 page label.png"),
    ([(65, 0, 9, 8, 8, 0, 0, 8)], "lies outside"),
    ([(65, 0, 0, 8, 8, 0, 0, 8), (66, 0, 0, 40, 4, 0, 0, 8), (67, 0, 20, 1, 1, 0, 0, 8)], "(and 1 more glyph(s))"),
])
def test_font_glyph_rect_out_of_bounds_is_typed_error(tmp_path, monkeypatch, fmt, chars, needle):
    src = _font(tmp_path, monkeypatch, fmt, chars)
    with pytest.raises(GstInputError) as e:
        font_to_godot.main([str(src), "-o", str(tmp_path / "t.tres")])
    assert needle in str(e.value) and "glyph check failed" in str(e.value)
    assert not (tmp_path / "t.tres").exists()                                      # nothing written on a bad font


def test_font_glyph_check_uses_the_real_page_and_other_failures(tmp_path, monkeypatch):
    # a font declaring a 16x16 page but shipping a 32x32 image: glyphs up to 32 are real, with a note
    src = _font(tmp_path, monkeypatch, "text", [(65, 20, 20, 8, 8, 0, 0, 8)], size=(32, 32))
    assert font_to_godot.main([str(src), "-o", str(tmp_path / "t.tres"), "--json", str(tmp_path / "r.json")]) == 0
    assert "differs from the page image" in json.load(open(tmp_path / "r.json"))["scale_note"]
    # a glyph on an undeclared page, and a negative text rect
    for body in (b"char id=65 x=0 y=0 width=4 height=4 xoffset=0 yoffset=0 xadvance=4 page=3 chnl=15\n",
                 b"char id=65 x=-2 y=0 width=4 height=4 xoffset=0 yoffset=0 xadvance=4 page=0 chnl=15\n"):
        raw = test_v21.bmfont_text().split(b"chars count")[0] + b"chars count=1\n" + body
        (tmp_path / "bad.fnt").write_bytes(raw)
        with pytest.raises(GstInputError):
            font_to_godot.main([str(tmp_path / "bad.fnt"), "-o", str(tmp_path / "t2.tres")])
    # a char line without a width, and a page that is not an image
    raw = test_v21.bmfont_text().split(b"chars count")[0] + b"chars count=1\nchar id=65 x=0 y=0 height=4 page=0\n"
    (tmp_path / "bad.fnt").write_bytes(raw)
    with pytest.raises(GstInputError):
        font_to_godot.main([str(tmp_path / "bad.fnt"), "-o", str(tmp_path / "t2.tres")])
    (tmp_path / "label.png").write_bytes(b"not a png")
    (tmp_path / "ok.fnt").write_bytes(test_v21.bmfont_text())
    with pytest.raises(GstInputError):
        font_to_godot.main([str(tmp_path / "ok.fnt"), "-o", str(tmp_path / "t3.tres")])


# ---------------------------------------------------------------- nav-to-godot cuts partly covered cells
import random
import nav_to_godot
from test_v21 import nav_map


def _outlines(tscn_text):
    m = re.search(r"^outlines = Array\[PackedVector2Array\]\(\[(.*)\]\)$", tscn_text, re.M)
    out = []
    for body in re.findall(r"PackedVector2Array\(([^)]*)\)", m.group(1)):
        v = [float(n) for n in body.split(",")]
        xs, ys = v[0::2], v[1::2]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _overlap(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _run_nav(tmp_path, colliders, extra=(), data=None, w=4, h=3, tile=16, name="n.tscn"):
    src = nav_map(tmp_path, data=data if data is not None else [0] * (w * h), tw=tile, th=tile, w=w, h=h)
    col = tmp_path / "col.json"
    col.write_text(json.dumps({"rects": [{"x": x, "y": y, "w": cw, "h": ch} for x, y, cw, ch in colliders]}))
    out = tmp_path / name
    assert nav_to_godot.main([str(src), "-o", str(out), "--colliders", str(col), "--json", str(tmp_path / "r.json"), *extra]) == 0
    return out, json.load(open(tmp_path / "r.json"))


def test_nav_partial_overlap_is_cut_not_blocked(tmp_path):
    # a wall 8 px wide in the middle of column 1 (x 20..28), full height of rows 0..1
    wall = (20, 0, 8, 32)
    out, rec = _run_nav(tmp_path, [wall])
    rects = _outlines(out.read_text())
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects)
    assert area == 64 * 48 - 8 * 32                                   # exactly the map minus the wall
    assert rec["cut_cells"] == 2 and rec["cut_pieces"] == 4 and rec["blocked_cells"] == 0
    assert not any(_overlap(r, (20, 0, 28, 32)) for r in rects)       # nothing walkable inside the wall
    def covers(rects, x0, y0, x1, y1):
        return any(r[0] <= x0 + 1e-9 and r[2] >= x1 - 1e-9 and r[1] <= y0 + 1e-9 and r[3] >= y1 - 1e-9 for r in rects)
    assert covers(rects, 16, 0, 20, 32) and covers(rects, 28, 0, 32, 32)
    # the old behaviour is one flag away
    out2, rec2 = _run_nav(tmp_path, [wall], extra=["--block-whole-cells"], name="old.tscn")
    area2 = sum((r[2] - r[0]) * (r[3] - r[1]) for r in _outlines(out2.read_text()))
    assert area2 == 64 * 48 - 16 * 32 and rec2["cut_pieces"] == 0


def test_nav_cut_slivers_overflow_and_edges(tmp_path):
    # exactly cell-aligned collider: no cutting at all
    out, rec = _run_nav(tmp_path, [(16, 16, 16, 16)])
    assert rec["cut_cells"] == 0 and rec["cut_pieces"] == 0 and rec["walkable"] == 11
    # a collider leaving a 0.5 px strip: the strip is dropped (default --min-piece 1), kept with --min-piece 0
    sliver = (0, 0, 15.5, 16)
    out, rec = _run_nav(tmp_path, [sliver])
    assert rec["dropped_slivers"] == 1 and rec["cut_pieces"] == 0 and rec["blocked_cells"] == 1
    out, rec = _run_nav(tmp_path, [sliver], extra=["--min-piece", "0"], name="s0.tscn")
    assert rec["cut_pieces"] == 1
    sliver_rects = _outlines(out.read_text())
    assert any(r[0] <= 15.5 + 1e-9 and r[2] >= 16 - 1e-9 and r[1] <= 0 + 1e-9 and r[3] >= 16 - 1e-9 for r in sliver_rects)
    # a collider spilling past the map edge only cuts inside the map
    out, rec = _run_nav(tmp_path, [(56, 40, 100, 100)], name="e.tscn")
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in _outlines(out.read_text()))
    assert area == 64 * 48 - 8 * 8
    # a cell crossed by more colliders than the cut limit is blocked whole, and says so
    many = [(1 + i * 0.2, 1, 0.1, 14) for i in range(nav_to_godot.MAX_CUTS_PER_CELL + 1)]
    out, rec = _run_nav(tmp_path, many, name="m.tscn")
    assert rec["overflow_cells"] == 1 and rec["blocked_cells"] == 1
    with pytest.raises(GstInputError):
        _run_nav(tmp_path, [wall for wall in [(20, 0, 8, 32)]], extra=["--min-piece", "-1"], name="x.tscn")


def test_nav_cut_random_property(tmp_path):
    rng = random.Random(22)
    for trial in range(40):
        w, h, tile = rng.randint(2, 6), rng.randint(2, 5), rng.choice([8, 16, 20])
        cols = []
        for _ in range(rng.randint(1, 6)):
            cols.append((rng.uniform(-5, w * tile), rng.uniform(-5, h * tile), rng.uniform(0.5, 3 * tile), rng.uniform(0.5, 3 * tile)))
        data = [rng.choice([0, 0, 0, 1]) for _ in range(w * h)]
        try:
            out, rec = _run_nav(tmp_path, cols, extra=["--min-piece", "0", "--solid-layer", "walls"], data=data, w=w, h=h, tile=tile, name="p%d.tscn" % trial)
            rects = _outlines(out.read_text())
        except GstInputError as e:                      # everything solid: the typed "no walkable tiles" error
            assert "no walkable" in str(e)
            rects = []
        for i, a in enumerate(rects):
            assert a[2] - a[0] > 0 and a[3] - a[1] > 0
            cx, cy = int(a[0] // tile), int(a[1] // tile)
            assert a[0] >= 0 and a[1] >= 0 and a[2] <= w * tile and a[3] <= h * tile, "piece off the map"
            for cy in range(int(a[1] // tile), int(-(-a[3] // tile))):
                for cx in range(int(a[0] // tile), int(-(-a[2] // tile))):
                    assert data[cy * w + cx] == 0, "piece on a solid tile"
            for c in cols:
                assert _overlap(a, (c[0], c[1], c[0] + c[2], c[1] + c[3])) < 1e-6, "piece inside a collider"
            for b in rects[i + 1:]:
                assert _overlap(a, b) < 1e-6, "pieces overlap"
        # coverage: every free cell area is accounted for (walkable minus the union of colliders), by sampling
        for _ in range(200):
            px, py = rng.uniform(0, w * tile), rng.uniform(0, h * tile)
            free = data[int(py // tile) * w + int(px // tile)] == 0 and not any(
                c[0] < px < c[0] + c[2] and c[1] < py < c[1] + c[3] for c in cols)
            inside = any(r[0] < px < r[2] and r[1] < py < r[3] for r in rects)
            assert free == inside, (trial, px, py)


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_nav_cut_scene_loads_in_godot(tmp_path):
    out, rec = _run_nav(tmp_path, [(20, 0, 8, 32)])
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "nav.tscn").write_text(out.read_text())
    (proj / "project.godot").write_text("config_version=5\n\n[application]\n\nconfig/name=\"gst-nav\"\n")
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var n: NavigationRegion2D = load("res://nav.tscn").instantiate()\n'
        '	var p: NavigationPolygon = n.navigation_polygon\n'
        '	var area := 0.0\n'
        '	for i in p.get_outline_count():\n'
        '		var o := p.get_outline(i)\n'
        '		area += (o[1].x - o[0].x) * (o[2].y - o[1].y)\n'
        '	print("NAV outlines=", p.get_outline_count(), " polygons=", p.get_polygon_count(), " area=", area)\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    n_out = len(_outlines(out.read_text()))
    assert "NAV outlines=%d polygons=%d area=%s" % (n_out, n_out, float(64 * 48 - 8 * 32)) in r.stdout, r.stdout


# ---------------------------------------------------------------- install.sh --venv
INSTALL_SH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "install.sh")


def _clean_env(home):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_CACHE_HOME": str(home / ".cache"), "PIP_CACHE_DIR": str(home / "pipcache"), "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    return env


def test_install_sh_venv_dry_run_plans_dev_requirements(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "prefix"
    r = subprocess.run(["bash", INSTALL_SH, "--venv", "--with-tests", "--dry-run", "--prefix", str(prefix)],
                       capture_output=True, text=True, env=_clean_env(home), timeout=60)
    assert r.returncode == 0, r.stderr
    assert "-m venv %s/venv" % prefix in r.stdout and "requirements.txt" in r.stdout and "requirements-dev.txt" in r.stdout
    assert not prefix.exists()                                       # a dry run writes nothing
    r2 = subprocess.run(["bash", INSTALL_SH, "--venv", "--dry-run", "--prefix", str(prefix)],
                        capture_output=True, text=True, env=_clean_env(home), timeout=60)
    assert "requirements-dev.txt" not in r2.stdout                   # without --with-tests, runtime requirements only
    assert "set -euo" not in subprocess.run(["bash", INSTALL_SH, "--help"], capture_output=True, text=True).stdout


@pytest.mark.skipif(not os.environ.get("GST_TEST_VENV"), reason="set GST_TEST_VENV=1 for the real pip install (needs PyPI)")
def test_install_sh_real_venv_install(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    prefix = tmp_path / "prefix"
    r = subprocess.run(["bash", INSTALL_SH, "--venv", "--prefix", str(prefix)], capture_output=True, text=True,
                       env=_clean_env(home), timeout=540)
    assert r.returncode == 0, r.stdout + r.stderr
    py = prefix / "venv" / "bin" / "python"
    out = subprocess.run([str(py), "-c", "import PIL, numpy, sys; print(sys.prefix, PIL.__file__)"], capture_output=True, text=True)
    assert str(prefix / "venv") in out.stdout                        # Pillow came from the venv, not the system
    v = subprocess.run([str(py), str(prefix / "gst"), "version"], capture_output=True, text=True, env=_clean_env(home))
    assert v.stdout.startswith("gamestudio-tools ")


# ---------------------------------------------------------------- structured (semantic) fuzz of the 2.2.0 inputs
JUNK = [None, "x", "", -1, 0, 2 ** 40, 1e308, -1e308, 0.5, [], {}, [1], {"a": 1}, True, "1e999", "9" * 40]


def _paths(node, prefix=()):
    yield prefix
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _paths(v, prefix + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _paths(v, prefix + (i,))


def _junk(doc, rng, n):
    import copy
    doc = copy.deepcopy(doc)
    for _ in range(n):
        paths = [p for p in _paths(doc) if p]
        if not paths:
            break
        path = rng.choice(paths)
        parent = doc
        for k in path[:-1]:
            parent = parent[k]
        if rng.random() < 0.15 and isinstance(parent, dict):
            del parent[path[-1]]
        else:
            parent[path[-1]] = copy.deepcopy(rng.choice(JUNK))
    return doc


def _expect_typed(fn):
    """Run fn; a GstInputError or a clean SystemExit is fine, anything else is a bug."""
    try:
        fn()
    except (GstInputError, SystemExit):
        pass


def test_structured_fuzz_new_inputs(tmp_path):
    import map_objects_to_godot, ase_json_import, font_to_godot, nav_to_godot
    rng = random.Random(2200)
    src, proj = tsx_project(tmp_path)
    base_map = json.load(open(src))
    # 1. map JSON with animated + collection tilesets, junk anywhere
    for i in range(250):
        doc = _junk(base_map, rng, rng.randint(1, 4))
        (proj / "f.json").write_text(json.dumps(doc))
        _expect_typed(lambda: map_objects_to_godot.main([str(proj / "f.json"), "-o", str(tmp_path / "f.tscn")]))
    # 2. external TSX with junk attribute values
    tsx_text = (proj / "atlas.tsx").read_text()
    coll_text = (proj / "coll.tsx").read_text()
    for i in range(250):
        for name, text in (("atlas.tsx", tsx_text), ("coll.tsx", coll_text)):
            def mut(m):
                return '%s="%s"' % (m.group(1), rng.choice(["", "x", "-1", "0", "99999999999", "1e9", "nan", "../x.png", "1.5"])) if rng.random() < 0.3 else m.group(0)
            (proj / name).write_text(re.sub(r'(\w+)="[^"]*"', mut, text if name == "atlas.tsx" else coll_text))
        _expect_typed(lambda: map_objects_to_godot.main([str(src), "-o", str(tmp_path / "f.tscn")]))
    (proj / "atlas.tsx").write_text(tsx_text)
    (proj / "coll.tsx").write_text(coll_text)
    # 3. Aseprite JSON
    ase = _ase_sheet([{"name": "a", "from": 0, "to": 2, "direction": "pingpong"}, {"name": "b", "from": 1, "to": 3, "repeat": 2}])
    for i in range(250):
        doc = _junk(ase, rng, rng.randint(1, 4))
        (tmp_path / "a.json").write_text(json.dumps(doc))
        _expect_typed(lambda: ase_json_import.main([str(tmp_path / "a.json"), "-o", str(tmp_path / "ao")]))
    # 4. colliders JSON on a real map
    nav_src = nav_map(tmp_path, name="nm.json", data=[0] * 12, tw=8, th=8, w=4, h=3)
    cols = {"tile": [8, 8], "rects": [{"x": 4, "y": 2.5, "w": 7, "h": 9}, {"x": 12, "y": 0, "w": 3.5, "h": 40}]}
    for i in range(250):
        doc = _junk(cols, rng, rng.randint(1, 3))
        (tmp_path / "c.json").write_text(json.dumps(doc))
        _expect_typed(lambda: nav_to_godot.main([str(nav_src), "-o", str(tmp_path / "nv.tscn"), "--colliders", str(tmp_path / "c.json")]))
    # 5. BMFont text with numbers replaced by junk
    Image.new("RGBA", (16, 16), (255, 255, 255, 255)).save(tmp_path / "label.png")
    fnt = test_v21.bmfont_text().decode()
    for i in range(250):
        txt = re.sub(r"=(-?\d+)", lambda m: "=%s" % rng.choice(["-1", "0", "99999", "x", "", "1e3", m.group(1)]) if rng.random() < 0.25 else m.group(0), fnt)
        (tmp_path / "j.fnt").write_text(txt)
        _expect_typed(lambda: font_to_godot.main([str(tmp_path / "j.fnt"), "-o", str(tmp_path / "j.tres")]))


def test_nav_colliders_with_enormous_values_are_typed_errors(tmp_path):
    for extra in ([], ["--block-whole-cells"]):
        with pytest.raises(GstInputError):
            _run_nav(tmp_path, [(1e308, 0, 1e308, 8)], extra=extra, name="big.tscn")
