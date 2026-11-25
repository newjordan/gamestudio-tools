"""Version 2.3.0 gap-closing tests (self-contained: no samples/ dependency)."""
import json, os, subprocess

import pytest
from gst_errors import GstInputError
from PIL import Image

import map_objects_to_godot
from test_batch31 import godot_bin, _isolate
from test_v21 import have_render, render_frame, tile_map


def _map(tmp, objs, orientation="orthogonal", **extra):
    doc = {"type": "map", "orientation": orientation, "width": 4, "height": 4,
           "tilewidth": 32, "tileheight": 16,
           "layers": [{"type": "objectgroup", "name": "o", "objects": objs}]}
    doc.update(extra)
    src = tmp / "m.json"
    src.write_text(json.dumps(doc))
    return src


def test_tile_to_screen_staggered_and_hex():
    # staggered isometric, staggeraxis=y (default), staggerindex=odd (default)
    p = map_objects_to_godot.Projection({
        "orientation": "staggered", "tilewidth": 32, "tileheight": 16, "height": 4,
    })
    assert p.stagger and p.stagger_axis == "y" and p.stagger_index == "odd"
    assert p.tile_to_screen(0, 0) == (0.0, 0.0)
    assert p.tile_to_screen(1, 0) == (32.0, 0.0)
    assert p.tile_to_screen(0, 1) == (16.0, 8.0)   # odd row shifted by columnWidth
    assert p.tile_to_screen(1, 1) == (48.0, 8.0)
    # object pixels stay identity (Tiled already stores screen coords)
    assert p.point(20, 40) == (20.0, 40.0)
    assert p.delta(8, 4) == (8.0, 4.0)

    even = map_objects_to_godot.Projection({
        "orientation": "staggered", "tilewidth": 32, "tileheight": 16, "height": 4,
        "staggeraxis": "y", "staggerindex": "even",
    })
    assert even.tile_to_screen(0, 0) == (16.0, 0.0)  # even rows shifted
    assert even.tile_to_screen(0, 1) == (0.0, 8.0)

    stx = map_objects_to_godot.Projection({
        "orientation": "staggered", "tilewidth": 32, "tileheight": 16, "height": 4,
        "staggeraxis": "x", "staggerindex": "odd",
    })
    assert stx.tile_to_screen(0, 0) == (0.0, 0.0)
    assert stx.tile_to_screen(1, 0) == (16.0, 8.0)   # odd column shifted down
    assert stx.tile_to_screen(0, 1) == (0.0, 16.0)

    # pointy-top hex: staggeraxis=y, hexsidelength on Y
    # tw=32 th=32 side=16 -> sideOffsetY=(32-16)//2=8, rowHeight=24, tile_h=32
    # pixelX = tx * 32, odd row += columnWidth=16; pixelY = ty * 24
    hx = map_objects_to_godot.Projection({
        "orientation": "hexagonal", "tilewidth": 32, "tileheight": 32, "height": 4,
        "staggeraxis": "y", "staggerindex": "odd", "hexsidelength": 16,
    })
    assert hx.tile_to_screen(0, 0) == (0.0, 0.0)
    assert hx.tile_to_screen(1, 0) == (32.0, 0.0)
    assert hx.tile_to_screen(0, 1) == (16.0, 24.0)
    assert hx.tile_to_screen(1, 1) == (48.0, 24.0)
    assert hx.point(10, 20) == (10.0, 20.0)  # objects stay in pixel space

    # flat-top hex: staggeraxis=x, hexsidelength on X
    flat = map_objects_to_godot.Projection({
        "orientation": "hexagonal", "tilewidth": 32, "tileheight": 32, "height": 4,
        "staggeraxis": "x", "staggerindex": "odd", "hexsidelength": 16,
    })
    assert flat.tile_to_screen(0, 0) == (0.0, 0.0)
    assert flat.tile_to_screen(0, 1) == (0.0, 32.0)
    assert flat.tile_to_screen(1, 0) == (24.0, 16.0)


def test_polyline_emits_line2d_not_filled_polygon(tmp_path):
    src = _map(tmp_path, [{"id": 1, "name": "path", "x": 4, "y": 8,
                           "polyline": [{"x": 0, "y": 0}, {"x": 16, "y": 0}, {"x": 16, "y": 8}]}])
    out = tmp_path / "objs.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--line-width", "3",
                                      "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["polylines"] == 1 and rec["orientation"] == "orthogonal"
    text = out.read_text()
    assert 'type="Line2D"' in text
    assert "closed = false" in text
    assert "width = 3" in text
    assert "points = PackedVector2Array(0, 0, 16, 0, 16, 8)" in text
    assert "build_mode = 1" in text
    assert 'type="CollisionPolygon2D"' in text
    # not a closed / filled-only polygon without Line2D
    assert text.count("build_mode = 1") == 1


def test_polyline_iso_is_projected_and_open(tmp_path):
    src = _map(tmp_path, [{"id": 1, "name": "path", "x": 16, "y": 0,
                           "polyline": [{"x": 0, "y": 0}, {"x": 16, "y": 0}]}],
               orientation="isometric")
    out = tmp_path / "objs.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["polylines"] == 1 and rec["orientation"] == "isometric"
    text = out.read_text()
    assert 'type="Line2D"' in text and "closed = false" in text and "build_mode = 1" in text
    # start of the line at the projected object origin; a 16-unit +x logical
    # delta becomes (16, 8) in screen space (tw=32, th=16)
    assert "points = PackedVector2Array(0, 0, 16, 8)" in text


def test_stagger_and_hex_maps_keep_pixel_objects(tmp_path):
    for extra in (
        {"orientation": "staggered", "staggeraxis": "y", "staggerindex": "odd"},
        {"orientation": "hexagonal", "staggeraxis": "x", "staggerindex": "even", "hexsidelength": 8},
    ):
        src = _map(tmp_path, [
            {"id": 1, "name": "box", "x": 20, "y": 24, "width": 16, "height": 8},
            {"id": 2, "name": "path", "x": 20, "y": 24,
             "polyline": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]},
        ], **extra)
        out = tmp_path / ("objs_%s.tscn" % extra["orientation"])
        assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
        rec = json.load(open(tmp_path / "r.json"))
        assert rec["orientation"] == extra["orientation"]
        assert rec["staggeraxis"] == extra["staggeraxis"]
        assert rec["staggerindex"] == extra["staggerindex"]
        text = out.read_text()
        assert 'metadata/orientation = "%s"' % extra["orientation"] in text
        assert 'metadata/staggeraxis = "%s"' % extra["staggeraxis"] in text
        # objects stay at their pixel coordinates (no diamond projection)
        assert "position = Vector2(20, 24)" in text
        # a rect is still axis-aligned, not a diamond CollisionPolygon2D
        assert "RectangleShape2D" in text
        assert "size = Vector2(16, 8)" in text
        assert 'type="Line2D"' in text
        if extra["orientation"] == "hexagonal":
            assert rec["hexsidelength"] == 8
            assert "metadata/hexsidelength = 8" in text


def test_polyline_needs_two_points(tmp_path):
    src = _map(tmp_path, [{"id": 1, "name": "path", "x": 0, "y": 0,
                           "polyline": [{"x": 0, "y": 0}]}])
    with pytest.raises(GstInputError, match="at least two points"):
        map_objects_to_godot.main([str(src), "-o", str(tmp_path / "o.tscn")])


def test_line_width_must_be_positive(tmp_path):
    src = _map(tmp_path, [{"id": 1, "name": "path", "x": 0, "y": 0,
                           "polyline": [{"x": 0, "y": 0}, {"x": 1, "y": 0}]}])
    with pytest.raises(GstInputError, match="line-width"):
        map_objects_to_godot.main([str(src), "-o", str(tmp_path / "o.tscn"), "--line-width", "0"])


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_polyline_and_stagger_load_in_godot(tmp_path):
    src = _map(tmp_path, [
        {"id": 1, "name": "path", "x": 8, "y": 12,
         "polyline": [{"x": 0, "y": 0}, {"x": 20, "y": 0}, {"x": 20, "y": 10}]},
        {"id": 2, "name": "box", "x": 4, "y": 4, "width": 8, "height": 8},
    ], orientation="staggered", staggeraxis="y", staggerindex="odd")
    proj = tmp_path / "proj"
    proj.mkdir()
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "objs.tscn"), "--line-width", "4"]) == 0
    (proj / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="gst-v23"\n')
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var s: PackedScene = load("res://objs.tscn")\n'
        '	if s == null:\n'
        '		quit(1)\n'
        '		return\n'
        '	var n: Node = s.instantiate()\n'
        '	print("ORIENT ", n.get_meta("orientation"))\n'
        '	print("AXIS ", n.get_meta("staggeraxis"))\n'
        '	print("INDEX ", n.get_meta("staggerindex"))\n'
        '	var line: Line2D = n.get_node("o/path/Line")\n'
        '	print("POINTS ", line.points)\n'
        '	print("CLOSED ", line.closed)\n'
        '	print("WIDTH ", line.width)\n'
        '	var shape: CollisionPolygon2D = n.get_node("o/path/Shape")\n'
        '	print("BUILD ", int(shape.build_mode))\n'
        '	print("POLY ", shape.polygon)\n'
        '	var box: Node2D = n.get_node("o/box")\n'
        '	print("BOX ", box.position)\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
                   env=env, capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    assert "ORIENT staggered" in r.stdout
    assert "AXIS y" in r.stdout
    assert "INDEX odd" in r.stdout
    assert "CLOSED false" in r.stdout
    assert "WIDTH 4.0" in r.stdout or "WIDTH 4" in r.stdout
    assert "BUILD 1" in r.stdout
    # Line2D points are local to the Area2D, which is already at (8, 12)
    assert "POINTS" in r.stdout
    assert "(0.0, 0.0)" in r.stdout or "(0, 0)" in r.stdout
    assert "(20.0, 0.0)" in r.stdout or "(20, 0)" in r.stdout
    assert "(20.0, 10.0)" in r.stdout or "(20, 10)" in r.stdout
    assert "BOX (4.0, 4.0)" in r.stdout or "BOX (4, 4)" in r.stdout


@pytest.mark.skipif(not have_render(), reason="needs GODOT_BIN and xvfb-run for a software-GL render")
def test_staggered_tile_object_renders_at_pixel_coords(tmp_path):
    # A 16x16 tile object at (20, 40) on a staggered map uses Tiled's
    # bottom-left anchor, so the sprite's top-left is (20, 24).
    src, proj = tile_map(tmp_path, [{"id": 1, "gid": 1, "x": 20, "y": 40, "width": 16, "height": 16}],
                         orientation="staggered", w=4, h=4, tw=32, th=16)
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "main.tscn")]) == 0
    img = render_frame(tmp_path, proj, 200, 128, frame=3)
    # quad tile: red, green / blue, yellow. Sample interiors of each quadrant.
    def pix(x, y):
        return img.getpixel((x, y))
    # sprite occupies [20,36) x [24,40)
    assert pix(23, 27)[0] > 200 and pix(23, 27)[1] < 40   # red
    assert pix(31, 27)[1] > 200 and pix(31, 27)[0] < 40   # green
    assert pix(23, 35)[2] > 200 and pix(23, 35)[0] < 40   # blue
    assert pix(31, 35)[0] > 200 and pix(31, 35)[1] > 200  # yellow
    # just outside the sprite, the clear colour is black
    assert pix(19, 27) == (0, 0, 0)
    assert pix(20, 23) == (0, 0, 0)


# ---------------------------------------------------------------- ase-json-import: rotated frames and slices
import ase_json_import
import atlas_to_godot


def _rot_sheet(tmp, slice_keys=None):
    """8x12 upright sprite packed 90° CW as 12x8 at (0, 0). Top-left is red."""
    upright = Image.new("RGBA", (8, 12), (0, 0, 255, 255))
    for x in range(8):
        for y in range(4):
            upright.putpixel((x, y), (255, 0, 0, 255))
    packed = upright.transpose(Image.Transpose.ROTATE_270)  # 90° CW
    assert packed.size == (12, 8)
    sheet = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    sheet.paste(packed, (0, 0))
    sheet.save(tmp / "hero.png")
    slices = [] if slice_keys is None else slice_keys
    doc = {
        "frames": {"hero 0": {
            "frame": {"x": 0, "y": 0, "w": 12, "h": 8},
            "rotated": True, "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": 8, "h": 12},
            "sourceSize": {"w": 8, "h": 12}, "duration": 100,
        }},
        "meta": {"image": "hero.png", "size": {"w": 12, "h": 8},
                 "frameTags": [{"name": "idle", "from": 0, "to": 0, "direction": "forward"}],
                 "slices": slices},
    }
    src = tmp / "hero.json"
    src.write_text(json.dumps(doc))
    return src, upright


def test_ase_json_import_keeps_rotated_frames(tmp_path):
    src, upright = _rot_sheet(tmp_path)
    assert ase_json_import.main([str(src), "-o", str(tmp_path / "out")]) == 0
    atlas = json.load(open(tmp_path / "out.json"))
    assert atlas["frames"]["hero 0"]["rotated"] is True
    assert atlas["frames"]["hero 0"]["frame"] == {"x": 0, "y": 0, "w": 12, "h": 8}
    # atlas-to-godot unpacks the same way it does for a TexturePacker atlas
    assert atlas_to_godot.main([str(tmp_path / "out.json"), "-o", str(tmp_path / "hero.tres"),
                                "--sheet", str(tmp_path / "hero.png"),
                                "--rotated-dir", str(tmp_path / "unrot"),
                                "--rotated-res", "res://unrot"]) == 0
    got = Image.open(tmp_path / "unrot" / "hero_0_unrot.png").convert("RGBA")
    assert got.tobytes() == upright.tobytes()


def test_ase_json_import_exports_slices_and_pivot(tmp_path):
    slices = [{
        "name": "button",
        "color": "#0000ffff",
        "keys": [{
            "frame": 0,
            "bounds": {"x": 0, "y": 0, "w": 8, "h": 12},
            "center": {"x": 2, "y": 2, "w": 4, "h": 8},
            "pivot": {"x": 4, "y": 6},
        }],
    }]
    src, upright = _rot_sheet(tmp_path, slices)
    assert ase_json_import.main([str(src), "-o", str(tmp_path / "out"), "--res", "res://art/"]) == 0
    rec = json.load(open(tmp_path / "out.slices.json"))
    sl = rec["slices"][0]
    assert sl["name"] == "button"
    key = sl["keys"][0]
    assert key["pivot"] == {"x": 4, "y": 6}
    assert key["insets"] == {"left": 2, "top": 2, "right": 2, "bottom": 2}
    assert (tmp_path / "out_button.png").is_file()
    assert (tmp_path / "out_button.tres").is_file()
    # cropped PNG is the upright canvas, not the packed 12x8 strip
    got = Image.open(tmp_path / "out_button.png").convert("RGBA")
    assert got.size == (8, 12)
    assert got.tobytes() == upright.tobytes()
    tres = (tmp_path / "out_button.tres").read_text()
    assert 'type="StyleBoxTexture"' in tres
    assert "texture_margin_left = 2.0" in tres and "texture_margin_top = 2.0" in tres
    assert "texture_margin_right = 2.0" in tres and "texture_margin_bottom = 2.0" in tres
    assert 'path="res://art/out_button.png"' in tres
    scene = (tmp_path / "out.slices.tscn").read_text()
    assert 'metadata/pivot = Vector2(4, 6)' in scene
    assert 'metadata/insets = Vector4(2, 2, 2, 2)' in scene
    assert "metadata/nine_slice = true" in scene
    assert "offset = Vector2(-4, -6)" in scene
    assert 'type="Sprite2D"' in scene


def test_ase_json_import_slice_without_keys_is_named_only(tmp_path):
    src, _ = _rot_sheet(tmp_path, [{"name": "hurtbox"}])
    atlas, clips, slices = ase_json_import.convert(json.loads(src.read_text()))
    assert [s["name"] for s in slices] == ["hurtbox"] and slices[0]["keys"] == []
    assert ase_json_import.main([str(src), "-o", str(tmp_path / "out")]) == 0
    scene = (tmp_path / "out.slices.tscn").read_text()
    assert '[node name="hurtbox" type="Node2D" parent="."]' in scene
    assert "StyleBoxTexture" not in scene


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_ase_json_import_slices_load_in_godot(tmp_path):
    slices = [{
        "name": "button",
        "keys": [{
            "frame": 0,
            "bounds": {"x": 0, "y": 0, "w": 8, "h": 12},
            "center": {"x": 2, "y": 2, "w": 4, "h": 8},
            "pivot": {"x": 4, "y": 6},
        }],
    }]
    src, _ = _rot_sheet(tmp_path, slices)
    proj = tmp_path / "proj"
    proj.mkdir()
    # write outputs into the Godot project so res:// paths resolve
    assert ase_json_import.main([str(src), "-o", str(proj / "out"), "--res", "res://"]) == 0
    (proj / "project.godot").write_text('config_version=5\n\n[application]\n\nconfig/name="gst-v23-ase"\n')
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var sb: StyleBoxTexture = load("res://out_button.tres")\n'
        '	if sb == null:\n'
        '		quit(1)\n'
        '		return\n'
        '	print("MARGIN ", sb.texture_margin_left, " ", sb.texture_margin_top, " ", '
        'sb.texture_margin_right, " ", sb.texture_margin_bottom)\n'
        '	print("TEX ", sb.texture != null, " ", sb.texture.get_size() if sb.texture else Vector2.ZERO)\n'
        '	var s: PackedScene = load("res://out.slices.tscn")\n'
        '	var n: Node = s.instantiate()\n'
        '	var button: Node2D = n.get_node("button")\n'
        '	print("PIVOT ", button.get_meta("pivot"))\n'
        '	print("NINE ", button.get_meta("nine_slice"))\n'
        '	print("INSETS ", button.get_meta("insets"))\n'
        '	var spr: Sprite2D = button.get_node("Sprite")\n'
        '	print("OFFSET ", spr.offset)\n'
        '	print("SIZE ", spr.texture.get_size())\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
                   env=env, capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    assert "MARGIN 2.0 2.0 2.0 2.0" in r.stdout or "MARGIN 2 2 2 2" in r.stdout
    assert "TEX true" in r.stdout
    assert "PIVOT (4.0, 6.0)" in r.stdout or "PIVOT (4, 6)" in r.stdout
    assert "NINE true" in r.stdout
    assert "OFFSET (-4.0, -6.0)" in r.stdout or "OFFSET (-4, -6)" in r.stdout
    assert "SIZE (8.0, 12.0)" in r.stdout or "SIZE (8, 12)" in r.stdout


# ---------------------------------------------------------------- nav-to-godot: merge cut pieces with neighbours
import nav_to_godot
from test_v22 import _run_nav, _outlines, _overlap


def test_merge_rects_joins_neighbours_and_keeps_l_shape():
    # two side-by-side boxes become one
    got, ok = nav_to_godot.merge_rects([(0, 0, 8, 8), (8, 0, 16, 8)])
    assert ok and got == [(0.0, 0.0, 16.0, 8.0)]
    # an L stays two rectangles (the greedy row-run merge)
    got, ok = nav_to_godot.merge_rects([(0, 0, 8, 16), (8, 0, 16, 8)])
    assert ok and len(got) == 2
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in got)
    assert area == 8 * 16 + 8 * 8
    assert nav_to_godot.merge_rects([])[0] == []
    assert nav_to_godot.merge_rects([(0, 0, 4, 4)])[0] == [(0.0, 0.0, 4.0, 4.0)]


def test_nav_cut_pieces_merge_with_neighbouring_cells(tmp_path):
    # wall 8 px wide in column 1, full height of rows 0..1: left and right
    # leftover strips merge with their neighbours instead of staying 4 tiny pieces.
    wall = (20, 0, 8, 32)
    out, rec = _run_nav(tmp_path, [wall])
    rects = _outlines(out.read_text())
    area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects)
    assert area == 64 * 48 - 8 * 32
    assert rec["cut_pieces"] == 4 and rec["rects_before_merge"] == 7
    assert rec["rects"] == 3 and rec["merged"] is True
    # the 16..20 and 28..32 strips are absorbed into larger rectangles
    assert any(r[0] == 0 and r[2] == 20 and r[1] == 0 and r[3] == 32 for r in rects)
    assert any(r[0] == 28 and r[2] == 64 and r[1] == 0 and r[3] == 32 for r in rects)
    assert not any(_overlap(r, (20, 0, 28, 32)) for r in rects)
