"""Version 2.1.0 gap-closing tests (self-contained: no samples/ dependency)."""
import json, math, os, shutil, struct, subprocess

import pytest
from gst_errors import GstInputError
from PIL import Image, ImageOps

import map_objects_to_godot
from test_batch31 import godot_bin, _isolate

FH, FV, FD = 0x80000000, 0x40000000, 0x20000000


def have_render():
    return bool(godot_bin()) and shutil.which("xvfb-run") is not None


def render_frame(tmp_path, proj, w, h, frame=3):
    """Import then render one frame of the project's main scene with software GL; return a PIL image."""
    env = _isolate(tmp_path)
    (proj / "project.godot").write_text(
        "config_version=5\n\n[application]\nconfig/name=\"gst-v21\"\nrun/main_scene=\"res://main.tscn\"\n\n"
        "[display]\nwindow/size/viewport_width=%d\nwindow/size/viewport_height=%d\nwindow/stretch/mode=\"disabled\"\n\n"
        "[rendering]\ntextures/canvas_textures/default_texture_filter=0\n"
        "environment/defaults/default_clear_color=Color(0, 0, 0, 1)\nrenderer/rendering_method=\"gl_compatibility\"\n" % (w, h))
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
                   env=env, capture_output=True, timeout=120)
    env.update({"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe"})
    out = tmp_path / "movie" / "frame.png"
    out.parent.mkdir()
    r = subprocess.run(["xvfb-run", "-a", "-s", "-screen 0 %dx%dx24" % (max(w, 320), max(h, 240)),
                        godot_bin(), "--display-driver", "x11", "--rendering-driver", "opengl3",
                        "--rendering-method", "gl_compatibility", "--disable-vsync", "--path", str(proj),
                        "--write-movie", str(out), "--fixed-fps", "10", "--quit-after", str(frame + 1)],
                       env=env, capture_output=True, timeout=120)
    f = tmp_path / "movie" / ("frame%08d.png" % frame)
    assert f.is_file(), r.stderr.decode()[-400:]
    return Image.open(f).convert("RGB")


def quad_tile(size=16):
    h = size // 2
    img = Image.new("RGBA", (size, size))
    for (qx, qy), c in (((0, 0), (255, 0, 0, 255)), ((1, 0), (0, 255, 0, 255)),
                        ((0, 1), (0, 0, 255, 255)), ((1, 1), (255, 255, 0, 255))):
        img.paste(c, (qx * h, qy * h, qx * h + h, qy * h + h))
    return img


def tiled_xform(img, gid):
    if gid & FD:
        img = img.transpose(Image.TRANSPOSE)
    if gid & FH:
        img = ImageOps.mirror(img)
    if gid & FV:
        img = ImageOps.flip(img)
    return img


def tile_map(tmp, objs, orientation="orthogonal", w=13, h=4, tw=16, th=16, sheet=None, tilesets=None):
    sheet = sheet or quad_tile()
    proj = tmp / "proj"
    proj.mkdir(exist_ok=True)
    full = Image.new("RGBA", (sheet.size[0] * 2, sheet.size[1]), (90, 90, 90, 255))
    full.paste(sheet, (0, 0))
    full.save(proj / "tiles.png")
    doc = {"type": "map", "orientation": orientation, "width": w, "height": h, "tilewidth": tw, "tileheight": th,
           "tilesets": tilesets or [{"firstgid": 1, "name": "t", "image": "tiles.png", "imagewidth": full.size[0],
                                      "imageheight": full.size[1], "tilewidth": sheet.size[0], "tileheight": sheet.size[1],
                                      "columns": 2, "tilecount": 2}],
           "layers": [{"type": "objectgroup", "name": "o", "objects": objs}]}
    src = tmp / "m.json"
    src.write_text(json.dumps(doc))
    return src, proj


def test_sprite_transform_all_flag_combos():
    for flags in range(8):
        gid = (FH if flags & 1 else 0) | (FV if flags & 2 else 0) | (FD if flags & 4 else 0)
        fh, fv, sx, sy, extra = map_objects_to_godot.sprite_transform(gid, 16, 16, 16, 16, 0)
        assert (sx, sy) == (1.0, 1.0)
        # the decomposition must reproduce Tiled's flip order on the unit square
        (uu, uv, vu, vv), _ = map_objects_to_godot.tile_flip_matrix(gid)
        fx, fy = (-1 if fh else 1), (-1 if fv else 1)
        c, s = round(math.cos(extra)), round(math.sin(extra))
        got = (c * fx * sx, -s * fy * sy, s * fx * sx, c * fy * sy)
        assert tuple(round(v, 6) for v in got) == (uu, uv, vu, vv)
    # diagonal swaps the scale axes for a non-square box
    fh, fv, sx, sy, extra = map_objects_to_godot.sprite_transform(FD, 32, 16, 16, 8, 0)
    assert extra == pytest.approx(math.pi / 2) and (sx, sy) == (1.0, 4.0) and fv and not fh


def test_map_objects_sprite_text(tmp_path):
    src, _ = tile_map(tmp_path, [
        {"id": 1, "name": "plain", "gid": 1, "x": 16, "y": 32, "width": 16, "height": 16, "type": "deco",
         "properties": [{"name": "layer", "value": 2}]},
        {"id": 2, "name": "flip", "gid": 2 | FH | FV, "x": 0, "y": 16, "width": 16, "height": 16},
        {"id": 3, "name": "ghost", "gid": 99, "x": 0, "y": 0, "width": 16, "height": 16},
    ])
    out = tmp_path / "o.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["sprites"] == 2
    assert rec["unknown_gids"] == 1 and rec["textures"] == ["res://tiles.png"]
    text = out.read_text()
    assert 'type="Sprite2D"' in text and "region_enabled = true" in text
    assert "region_rect = Rect2(0, 0, 16, 16)" in text            # gid 1 is atlas cell 0
    assert "region_rect = Rect2(16, 0, 16, 16)" in text           # gid 2 is atlas cell 1
    assert "flip_h = true" in text and "flip_v = true" in text
    assert "position = Vector2(16, 16)" in text                   # bottom-left anchor -> top-left y - h
    assert 'metadata/layer = 2' in text and 'metadata/tiled_type = "deco"' in text
    # the unmatched GID stays a marker that still carries its GID
    assert 'type="Marker2D"' in text and "metadata/gid = 99" in text
    assert map_objects_to_godot.main([str(src), "-o", str(tmp_path / "n.tscn"), "--no-sprites"]) == 0
    assert 'type="Sprite2D"' not in (tmp_path / "n.tscn").read_text()


def test_map_objects_isometric_projection(tmp_path):
    objs = [
        {"id": 1, "name": "tree", "gid": 1, "x": 16, "y": 16, "width": 32, "height": 32},
        {"id": 2, "name": "zone", "x": 0, "y": 0, "width": 16, "height": 16},
        {"id": 3, "name": "mark", "x": 16, "y": 0, "point": True, "width": 0, "height": 0},
    ]
    src, _ = tile_map(tmp_path, objs, orientation="isometric", w=4, h=4, tw=32, th=16,
                      sheet=quad_tile(32))
    out = tmp_path / "iso.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out)]) == 0
    text = out.read_text()
    # logical (16,16) is tile (1,1): screen x = 0 + 4*32/2 = 64, y = 16; iso objects align at bottom-centre
    assert "position = Vector2(48, -16)" in text
    # a 16x16 logical rectangle projects to a diamond polygon
    assert "polygon = PackedVector2Array(0, 0, 16, 8, 0, 16, -16, 8)" in text
    assert 'type="CollisionPolygon2D"' in text
    # point at logical (16, 0) = tile (1, 0): x = 64 + 16 = 80, y = 8
    assert "position = Vector2(80, 8)" in text


def test_map_objects_staggered_uses_pixels(tmp_path):
    src, _ = tile_map(tmp_path, [{"id": 1, "gid": 1, "x": 20, "y": 40, "width": 16, "height": 16}],
                      orientation="staggered", w=4, h=4)
    out = tmp_path / "s.tscn"
    assert map_objects_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    assert json.load(open(tmp_path / "r.json"))["orientation"] == "staggered"
    assert "position = Vector2(20, 24)" in out.read_text()


@pytest.mark.skipif(not have_render(), reason="needs GODOT_BIN and xvfb-run for a software-GL render")
def test_map_objects_sprites_render_in_godot(tmp_path):
    """Render Sprite2D tile objects in official Godot and compare pixels with Tiled's flip semantics."""
    combos = [0, FH, FV, FH | FV, FD, FD | FH, FD | FV, FD | FH | FV]
    objs = [{"id": i + 1, "gid": 1 | f, "x": 4 + i * 24, "y": 28, "width": 16, "height": 16}
            for i, f in enumerate(combos)]
    # a 2x scaled copy with a diagonal flip, and a quarter-turn rotation about the bottom-left anchor
    objs.append({"id": 20, "gid": 1 | FD | FH, "x": 8, "y": 96, "width": 32, "height": 32})
    objs.append({"id": 21, "gid": 1, "x": 100, "y": 80, "width": 16, "height": 16, "rotation": 90})
    src, proj = tile_map(tmp_path, objs, w=13, h=8)
    assert map_objects_to_godot.main([str(src), "-o", str(proj / "main.tscn")]) == 0
    got = render_frame(tmp_path, proj, 200, 128)
    exp = Image.new("RGBA", (200, 128), (0, 0, 0, 255))
    tile = quad_tile()
    for o in objs[:8]:
        exp.paste(tiled_xform(tile, o["gid"]), (o["x"], o["y"] - 16))
    big = tiled_xform(tile, objs[8]["gid"]).resize((32, 32), Image.NEAREST)
    exp.paste(big, (8, 96 - 32))
    exp.paste(tile.rotate(-90), (100, 80))        # 90 degrees clockwise about (x, y)
    exp = exp.convert("RGB")
    bad = [(x, y) for y in range(128) for x in range(200) if got.getpixel((x, y)) != exp.getpixel((x, y))]
    assert not bad, "%d pixels differ, first %s" % (len(bad), bad[:5])


# ---------------------------------------------------------------- ase-to-godot directions
import ase_to_godot


def write_ase_frames(path, w, h, colors, durations, tags):
    """Multi-frame 32-bit Aseprite file: one layer, one raw cel per frame, tags as (name, from, to, dir, repeat)."""
    def pstr(s):
        b = s.encode("utf-8")
        return struct.pack("<H", len(b)) + b

    layer_payload = struct.pack("<HHHHHHB", 1, 0, 0, 0, 0, 0, 255) + b"\x00\x00\x00" + pstr("Layer 1")
    layer_chunk = struct.pack("<IH", 6 + len(layer_payload), 0x2004) + layer_payload
    frames = b""
    for i, (col, dur) in enumerate(zip(colors, durations)):
        rgba = bytes(col) * (w * h)
        cel = struct.pack("<HhhBH", 0, 0, 0, 255, 0) + b"\x00" * 7 + struct.pack("<HH", w, h) + rgba
        chunks = (layer_chunk if i == 0 else b"") + struct.pack("<IH", 6 + len(cel), 0x2005) + cel
        n = 2 if i == 0 else 1
        if i == 0 and tags:
            body = struct.pack("<H", len(tags)) + b"\x00" * 8
            for name, frm, to, direction, repeat in tags:
                body += struct.pack("<HHBH", frm, to, direction, repeat) + b"\x00" * 6 + b"\xff\x00\x00\x00" + pstr(name)
            chunks += struct.pack("<IH", 6 + len(body), 0x2018) + body
            n += 1
        frames += struct.pack("<IHHH2sI", 16 + len(chunks), 0xF1FA, n, dur, b"\x00\x00", 0) + chunks
    header = bytearray(128)
    struct.pack_into("<IHHHHHIH", header, 0, 128 + len(frames), 0xA5E0, len(colors), w, h, 32, 1, durations[0])
    struct.pack_into("<H", header, 32, 256)
    path.write_bytes(bytes(header) + frames)
    return path


def test_expand_tag_directions():
    e = ase_to_godot.expand_tag
    assert e(1, 4, "forward", 0) == ([1, 2, 3, 4], True)
    assert e(1, 4, "reverse", 0) == ([4, 3, 2, 1], True)
    assert e(1, 4, "pingpong", 0) == ([1, 2, 3, 4, 3, 2], True)
    assert e(1, 4, "pingpong_reverse", 0) == ([4, 3, 2, 1, 2, 3], True)
    assert e(2, 3, "pingpong", 0) == ([2, 3], True) and e(5, 5, "pingpong", 0) == ([5], True)
    assert e(0, 2, "forward", 1) == ([0, 1, 2], False)
    assert e(0, 2, "forward", 2) == ([0, 1, 2, 0, 1, 2], False)
    assert e(0, 2, "pingpong", 1) == ([0, 1, 2, 1, 0], False)
    assert e(0, 1, "reverse", 1) == ([1, 0], False)
    seq, loop = e(0, 9, "forward", 65535)                 # absurd repeat is clamped
    assert not loop and len(seq) <= ase_to_godot.MAX_CLIP_FRAMES


def test_ase_to_godot_expands_directions(tmp_path):
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    src = write_ase_frames(tmp_path / "hero.ase", 2, 2, colors, [100, 200, 300, 400], [
        ("walk", 0, 3, 0, 0), ("back", 0, 3, 1, 0), ("wobble", 0, 3, 2, 0),
        ("wob_rev", 0, 3, 3, 0), ("once", 1, 2, 0, 1), ("twice_pp", 0, 2, 2, 2)])
    out = tmp_path / "hero.tres"
    assert ase_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    c = rec["clips"]
    assert c["walk"] == {"direction": "forward", "loop": True, "frames": 4}
    assert c["back"]["direction"] == "reverse" and c["back"]["frames"] == 4
    assert c["wobble"]["frames"] == 6 and c["wobble"]["loop"] is True
    assert c["wob_rev"]["frames"] == 6
    assert c["once"] == {"direction": "forward", "loop": False, "frames": 2}
    assert c["twice_pp"]["loop"] is False and c["twice_pp"]["frames"] == 9    # (0 1 2 1) x2 + 0
    text = out.read_text()
    tex = {}
    for line in text.splitlines():
        if line.startswith("[ext_resource"):
            tex[line.split('id="')[1].split('"')[0]] = line.split('path="')[1].split('"')[0].rsplit("_", 1)[1]
    # pull each animation's frame order and loop flag from the .tres
    import re
    anims, blocks = {}, {}
    for m in re.finditer(r'\{\s*"frames": \[(.*?)\],\s*"loop": (true|false),\s*"name": &"(\w+)"', text, re.S):
        ids = re.findall(r'"texture": ExtResource\("([^"]+)"\)', m.group(1))
        anims[m.group(3)] = ([int(tex[i].split(".")[0]) for i in ids], m.group(2) == "true")
        blocks[m.group(3)] = m.group(1)
    assert anims["back"] == ([3, 2, 1, 0], True)
    assert anims["wobble"] == ([0, 1, 2, 3, 2, 1], True)
    assert anims["wob_rev"] == ([3, 2, 1, 0, 1, 2], True)
    assert anims["once"] == ([1, 2], False)
    assert anims["twice_pp"] == ([0, 1, 2, 1, 0, 1, 2, 1, 0], False)
    # durations follow the expanded frames
    wob = blocks["wobble"]
    assert [float(x) for x in re.findall(r'"duration": ([0-9.]+)', wob)] == pytest.approx(
        [d / (1000.0 / 12) for d in (100, 200, 300, 400, 300, 200)])
    # --ignore-direction plays everything forward and looping
    out2 = tmp_path / "flat.tres"
    assert ase_to_godot.main([str(src), "-o", str(out2), "--ignore-direction", "--json", str(tmp_path / "r2.json")]) == 0
    c2 = json.load(open(tmp_path / "r2.json"))["clips"]
    assert all(v["direction"] == "forward" and v["loop"] for v in c2.values())


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_ase_to_godot_directions_load_in_godot(tmp_path):
    colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
    src = write_ase_frames(tmp_path / "hero.ase", 2, 2, colors, [100, 100, 100, 100], [
        ("back", 0, 3, 1, 0), ("wobble", 0, 3, 2, 0), ("once", 1, 2, 0, 1)])
    proj = tmp_path / "proj"
    proj.mkdir()
    assert ase_to_godot.main([str(src), "-o", str(proj / "hero.tres"), "--frames-dir", str(proj / "f"),
                              "--res", "res://f/"]) == 0
    (proj / "project.godot").write_text("config_version=5\n\n[application]\n\nconfig/name=\"gst-ase\"\n")
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	var sf: SpriteFrames = load("res://hero.tres")\n'
        '	if sf == null:\n'
        '		quit(1)\n'
        '		return\n'
        '	for n in ["back", "wobble", "once"]:\n'
        '		var order := []\n'
        '		for i in sf.get_frame_count(n):\n'
        '			order.append(sf.get_frame_texture(n, i).resource_path.get_file().substr(6, 4).to_int())\n'
        '		print("ANIM ", n, " ", order, " loop=", sf.get_animation_loop(n))\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
                   env=env, capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    assert "ANIM back [3, 2, 1, 0] loop=true" in r.stdout
    assert "ANIM wobble [0, 1, 2, 3, 2, 1] loop=true" in r.stdout
    assert "ANIM once [1, 2] loop=false" in r.stdout


# ---------------------------------------------------------------- font-to-godot formats
import font_to_godot

FONT_CHARS = [(65, 0, 0, 6, 8, 0, 0, 6), (66, 6, 0, 6, 8, 0, 0, 6), (32, 12, 0, 3, 8, 0, 0, 3)]


def bmfont_text(page="label.png"):
    s = ('info face="tiny" size=8 bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 padding=0,0,0,0 spacing=1,1\n'
         "common lineHeight=8 base=6 scaleW=16 scaleH=16 pages=1 packed=0\n"
         'page id=0 file="%s"\nchars count=%d\n' % (page, len(FONT_CHARS)))
    for c in FONT_CHARS:
        s += "char id=%d x=%d y=%d width=%d height=%d xoffset=%d yoffset=%d xadvance=%d page=0 chnl=15\n" % c
    return s.encode()


def bmfont_xml(page="label.png"):
    s = ('<?xml version="1.0"?>\n<font>\n <info face="tiny" size="8" bold="0" italic="0" charset="" unicode="1" '
         'stretchH="100" smooth="0" aa="1" padding="0,0,0,0" spacing="1,1"/>\n'
         ' <common lineHeight="8" base="6" scaleW="16" scaleH="16" pages="1" packed="0"/>\n'
         ' <pages><page id="0" file="%s"/></pages>\n <chars count="%d">\n' % (page, len(FONT_CHARS)))
    for c in FONT_CHARS:
        s += '  <char id="%d" x="%d" y="%d" width="%d" height="%d" xoffset="%d" yoffset="%d" xadvance="%d" page="0" chnl="15"/>\n' % c
    return (s + " </chars>\n</font>\n").encode()


def bmfont_binary(page="label.png", kerning=((65, 66, -1),)):
    def block(kind, data):
        return struct.pack("<BI", kind, len(data)) + data
    info = struct.pack("<hBBHBBBBBBBB", 8, 0, 0, 100, 1, 0, 0, 0, 0, 1, 1, 0) + b"tiny\x00"
    common = struct.pack("<HHHHHBBBBB", 8, 6, 16, 16, 1, 0, 0, 0, 0, 0)
    pages = page.encode() + b"\x00"
    chars = b"".join(struct.pack("<IHHHHhhhBB", c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], 0, 15) for c in FONT_CHARS)
    out = b"BMF\x03" + block(1, info) + block(2, common) + block(3, pages) + block(4, chars)
    if kerning:
        out += block(5, b"".join(struct.pack("<IIh", *k) for k in kerning))
    return out


@pytest.mark.parametrize("fmt,maker", [("text", bmfont_text), ("xml", bmfont_xml), ("binary", bmfont_binary)])
def test_font_to_godot_formats(tmp_path, fmt, maker):
    Image.new("RGBA", (16, 16), (255, 255, 255, 255)).save(tmp_path / "label.png")
    src = tmp_path / "label.fnt"
    src.write_bytes(maker())
    out = tmp_path / "theme.tres"
    assert font_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json"),
                               "--copy-dir", str(tmp_path / "fonts"), "--res", "res://fonts/"]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["format"] == fmt and rec["chars"] == 3 and rec["size"] == 8 and rec["pages"] == ["label.png"]
    name = "label_text.fnt" if fmt == "xml" else "label.fnt"      # XML is converted: Godot cannot import it
    assert 'path="res://fonts/%s"' % name in out.read_text()
    assert (tmp_path / "fonts" / name).is_file() and (tmp_path / "fonts" / "label.png").is_file()
    if fmt == "xml":
        conv = font_to_godot.parse_text((tmp_path / "fonts" / name).read_text())
        assert conv["chars"] == 3 and conv["pages"] == ["label.png"] and conv["line_height"] == 8


def test_font_to_godot_rejects_bad_binary_and_xml(tmp_path):
    Image.new("RGBA", (16, 16)).save(tmp_path / "label.png")
    good = bmfont_binary()
    cases = {
        "v2": b"BMF\x02" + good[4:],
        "trunc_header": good[:8],
        "long_block": good[:5] + struct.pack("<I", 9999) + good[9:],
        "no_chars": b"BMF\x03" + good[4:].split(b"\x04", 1)[0][:-0 or None],
        "bad_chars_len": good.replace(struct.pack("<BI", 4, 60), struct.pack("<BI", 4, 59)),
        "xml_wrong_root": b"<map/>",
        "xml_garbage": b"<font><info",
        "xml_no_page": b"<font><info size='8'/><chars><char id='1'/></chars></font>",
        "xml_no_chars": b'<font><pages><page id="0" file="label.png"/></pages></font>',
    }
    for name, raw in cases.items():
        src = tmp_path / ("%s.fnt" % name)
        src.write_bytes(raw)
        with pytest.raises(font_to_godot.GstInputError):
            font_to_godot.main([str(src), "-o", str(tmp_path / "o.tres")])


def test_font_to_godot_multi_page_copy(tmp_path):
    Image.new("RGBA", (16, 16)).save(tmp_path / "p0.png")
    Image.new("RGBA", (16, 16)).save(tmp_path / "p1.png")
    text = bmfont_text("p0.png").decode().replace('page id=0 file="p0.png"\n', 'page id=0 file="p0.png"\npage id=1 file="p1.png"\n')
    (tmp_path / "m.fnt").write_text(text)
    assert font_to_godot.main([str(tmp_path / "m.fnt"), "-o", str(tmp_path / "t.tres"),
                               "--copy-dir", str(tmp_path / "out")]) == 0
    assert sorted(os.listdir(tmp_path / "out")) == ["m.fnt", "p0.png", "p1.png"]
    (tmp_path / "gone.fnt").write_text(text.replace("p1.png", "nope.png"))
    with pytest.raises(font_to_godot.GstInputError):
        font_to_godot.main([str(tmp_path / "gone.fnt"), "-o", str(tmp_path / "t2.tres")])


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_font_to_godot_binary_and_xml_load_in_godot(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    Image.new("RGBA", (16, 16), (255, 255, 255, 255)).save(proj / "label.png")
    for fmt, maker in (("text", bmfont_text), ("xml", bmfont_xml), ("binary", bmfont_binary)):
        (proj / ("f_%s.fnt" % fmt)).write_bytes(maker("f_%s.png" % fmt))
        (proj / ("f_%s.png" % fmt)).write_bytes((proj / "label.png").read_bytes())
        assert font_to_godot.main([str(proj / ("f_%s.fnt" % fmt)), "-o", str(proj / ("t_%s.tres" % fmt)),
                                   "--copy-dir", "."]) == 0
    (proj / "project.godot").write_text("config_version=5\n\n[application]\n\nconfig/name=\"gst-font\"\n")
    (proj / "check.gd").write_text(
        'extends SceneTree\n'
        'func _init() -> void:\n'
        '	for fmt in ["text", "xml", "binary"]:\n'
        '		var th: Theme = load("res://t_%s.tres" % fmt)\n'
        '		if th == null or th.default_font == null:\n'
        '			print("FONT ", fmt, " FAILED")\n'
        '			continue\n'
        '		var f: Font = th.default_font\n'
        '		print("FONT ", fmt, " AB=", f.get_string_size("AB", HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x, " h=", f.get_height(8))\n'
        '	quit(0)\n')
    env = _isolate(tmp_path)
    subprocess.run([godot_bin(), "--headless", "--path", str(proj), "--import", "--quit"],
                   env=env, capture_output=True, timeout=120)
    r = subprocess.run([godot_bin(), "--headless", "--path", str(proj), "-s", "res://check.gd"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60, text=True)
    assert r.returncode == 0, r.stdout
    for fmt in ("text", "xml"):
        assert "FONT %s AB=12.0 h=8.0" % fmt in r.stdout, r.stdout     # XML goes through the text conversion
    assert "FONT binary AB=11.0 h=8.0" in r.stdout, r.stdout      # the -1 kerning pair A,B applies


# ---------------------------------------------------------------- nav-to-godot + tile-colliders
import nav_to_godot, tile_colliders


def nav_map(tmp_path, name="level.json", data=None, tw=8, th=8, w=4, h=2):
    data = data if data is not None else [0, 0, 1, 1, 0, 0, 1, 1]
    src = tmp_path / name
    src.write_text(json.dumps({
        "type": "map", "width": w, "height": h, "tilewidth": tw, "tileheight": th,
        "layers": [{"type": "tilelayer", "name": "walls", "width": w, "height": h, "data": data}]}))
    return src


def test_nav_to_godot_picks_up_sibling_tile_colliders(tmp_path):
    src = nav_map(tmp_path)
    ref = tmp_path / "ref.tscn"
    assert nav_to_godot.main([str(src), "-o", str(ref), "--solid-layer", "walls"]) == 0
    # tile-colliders writes <stem>.colliders.json next to the map: nav-to-godot uses it with no flags
    assert tile_colliders.main([str(src), "-o", str(tmp_path / "level.colliders.json")]) == 0
    out = tmp_path / "nav.tscn"
    assert nav_to_godot.main([str(src), "-o", str(out), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["colliders_source"] == "auto" and rec["colliders"].endswith("level.colliders.json")
    assert rec["walkable"] == 4 and out.read_text() == ref.read_text()
    # --no-colliders switches it off: everything walkable
    assert nav_to_godot.main([str(src), "-o", str(out), "--no-colliders", "--json", str(tmp_path / "r2.json")]) == 0
    r2 = json.load(open(tmp_path / "r2.json"))
    assert r2["walkable"] == 8 and r2["colliders"] is None and r2["colliders_source"] is None
    # explicit --solid-layer / --solid-ids mean the user chose the solids: no auto pickup
    assert nav_to_godot.main([str(src), "-o", str(out), "--solid-ids", "99", "--json", str(tmp_path / "r3.json")]) == 0
    assert json.load(open(tmp_path / "r3.json"))["colliders"] is None


def test_nav_to_godot_colliders_flag_forms_and_combination(tmp_path):
    src = nav_map(tmp_path, data=[0] * 8)                       # no solids in the map itself
    objs = tmp_path / "col_objs.json"                           # --tiled-objects form, 8x8 tiles
    objs.write_text(json.dumps({"type": "objectgroup", "name": "collision", "objects": [
        {"id": 1, "x": 8, "y": 0, "width": 8, "height": 16}]}))
    out = tmp_path / "nav.tscn"
    assert nav_to_godot.main([str(src), "-o", str(out), "--colliders", str(objs), "--json", str(tmp_path / "r.json")]) == 0
    rec = json.load(open(tmp_path / "r.json"))
    assert rec["colliders_source"] == "flag" and rec["walkable"] == 6 and rec["rects"] == 2
    # a rect file combined with --solid-layer: both sets of solids apply
    src2 = nav_map(tmp_path, name="m2.json", data=[0, 0, 0, 1, 0, 0, 0, 0])
    rects = tmp_path / "rects.json"
    rects.write_text(json.dumps({"tile": [8, 8], "rects": [{"x": 0, "y": 8, "w": 8, "h": 8}]}))
    assert nav_to_godot.main([str(src2), "-o", str(out), "--colliders", str(rects), "--solid-layer", "walls",
                              "--json", str(tmp_path / "r2.json")]) == 0
    assert json.load(open(tmp_path / "r2.json"))["walkable"] == 8 - 1 - 1
    # a rectangle that is off the map or half a tile wide still blocks only the cells it overlaps
    part = tmp_path / "part.json"
    part.write_text(json.dumps({"rects": [{"x": 4, "y": -50, "w": 8, "h": 200}, {"x": 900, "y": 0, "w": 8, "h": 8}]}))
    assert nav_to_godot.main([str(src), "-o", str(out), "--colliders", str(part), "--json", str(tmp_path / "r3.json")]) == 0
    assert json.load(open(tmp_path / "r3.json"))["walkable"] == 4      # columns 0 and 1 blocked


def test_nav_to_godot_colliders_errors(tmp_path):
    src = nav_map(tmp_path)
    out = tmp_path / "nav.tscn"
    bad = {
        "tile_size": {"tile": [16, 16], "rects": []},
        "no_list": {"hello": 1},
        "array": [1, 2],
        "string_x": {"rects": [{"x": "a", "y": 0, "w": 8, "h": 8}]},
        "nan": '{"rects": [{"x": NaN, "y": 0, "w": 8, "h": 8}]}',
        "bad_tile": {"tile": "8x8", "rects": []},
        "not_object": {"rects": [5]},
        "everything_solid": {"tile": [8, 8], "rects": [{"x": 0, "y": 0, "w": 100, "h": 100}]},
    }
    for name, doc in bad.items():
        f = tmp_path / ("%s.json" % name)
        f.write_text(doc if isinstance(doc, str) else json.dumps(doc))
        with pytest.raises(nav_to_godot.GstInputError):
            nav_to_godot.main([str(src), "-o", str(out), "--colliders", str(f)])
    (tmp_path / "junk.json").write_text("{")
    with pytest.raises(nav_to_godot.GstInputError):
        nav_to_godot.main([str(src), "-o", str(out), "--colliders", str(tmp_path / "junk.json")])
    # a malformed sibling file is an error too, not silently skipped; --no-colliders is the way out
    (tmp_path / "level.colliders.json").write_text("[]")
    with pytest.raises(nav_to_godot.GstInputError):
        nav_to_godot.main([str(src), "-o", str(out)])
    assert nav_to_godot.main([str(src), "-o", str(out), "--no-colliders"]) == 0
    # the output may not overwrite the colliders file
    with pytest.raises(SystemExit):
        nav_to_godot.main([str(src), "-o", str(tmp_path / "level.colliders.json"), "--no-colliders", "--colliders",
                           str(tmp_path / "level.colliders.json")])


# ---------------------------------------------------------------- zstd_pure
import base64, hashlib, zstd_pure

# (name, length, sha256, base64 frame) produced by the reference zstd library at test-writing time
ZSTD_VECTORS = [
    ('words (sequences, Huffman literals)', 684, '6bef13b24691cdd123869983f05c49e60a7ddc3b0991e9004c74a736614041cf',
     'KLUv/WCsAQUGAEQDdGhlIHRpbGUgd2FsbHMgb2JqZWN0cyBxdWlja3RoZXpzdGQgZ3JvdW5kbGF5ZXJ3YWxsc0mo'
     '0ZfCzt4BEBID1Z0HEUAkjkkjXVFlOIsF4s1Gd0hUOOXTAKQESXHjnimyC04CggiC9wmcTLP12DdpMGPwePA/wGz6'
     'GrVA55onz/+c4nuLuhd3qO97KN6TD314oxV0+wuZfqcrS8EFApknHV6CPKtsnNH5VSnTAiTah46AgUoMNFNpPMTT'
     'FJeUKg=='),
    ('gids (checksum, content size)', 1600, '1f0dae2330be43e219b8be9f1312078b359b38469ead9e76bbe716cae944df66',
     'KLUv/WRABSUIAPJHCwvgGcYAICieraXcKeAAAJ+WouWj5/5xulJgxuDnpB+jRcv/d/11cCAOI2C+D2yoMd6lqbS/'
     'ATDIkCm6OxEgBAhGoBDRCAhpaaykMevwFWCcJH/FR+3OPLqvRvPSe/9bRhCPzGPTS/P+aXP4b3g5ye3+H2w9Tht6'
     '8WXev7y4DTJn4EN45zaGu+BS/hw74OL1fRBDxlH6lV35H12HG5e6qAezywukh8pSvf/4zPcJDtvOdNn0n+S7BNOx'
     'Q1iwbBqyj/zntd0aWv/CcOc9gbAOdoncwS+FL+fLfMKWzz7Vi2w51S/L4xzuZLw+4qRMH3pxUOWp97tNvXhfTxYg'
     '3LznZEANCDF0iQ=='),
    ('four-stream literals', 2500, '137f2781eafe6e11ebb367cb502b43f507ed5333e255b8c51b51aa83c5b05f82',
     'KLUv/WDECLUhAIa6YQnQ50RIEpkAaAlbAFsAYAB7XQDlq0WjQeIbMA8YgeflOYuMsRpfMX3FlKrHsXBTI2LuLyqL'
     'RwchnDam0EhHAXC7IOSttQmv4cxSPGyQ9HiGsSZhM0tQhiiXIUTtaSjgx6d8WSYEZQ7ZW66s8dEumyXIQHq1RU8F'
     'wEEHqLAHyLN0zkFM6STbCi1O3qao+4asYXmagHWgZf3LB4b377PNIyGzkSbmxydyooEr8kyFbtk/cCdl+MKAGBgb'
     'QWAUotjLBm21Xu+7EYV9iH/lB1RISKZgpKFa3ukELLowW7gmMICfGOCgUx+5GUHdYkYJ9K1MR6KCUKqCuoOPJXCA'
     'iGNxSPvAACA0jQSnIkEGZtSYAUw7IjElzSDQJwowBZxTZGRCBSlubeS4EsM/W10fklshKAXLeZTBTNwSZh0ByRIz'
     'zBQ+K5pxVkgydoUZ+YbMuxFwWUxmpqsiARoMtugO2N20MSGM2agc22J3Zt7PgoBy64RiYO6AQlE7oZGUesK2mSVg'
     'gQ2l1VQyCoFqqFEtZIhGRCQpSJIOIQQIAlEgSTYfESBvHSGB33PGfv53wUjlXdyQQnhFnmNKmxGzIfneHsKeHUSm'
     '9R3o1eegADWlBAqSjgvJbRnT6YtpWeoLXnKZR8l4mhAZwW74wKUxMJLE8dMwYutT3f259VcPr1er3fmBgmkl/5SA'
     'UWgFQkGxevoHWDL3+iC7URy4/6D0+3oQ7x4lN7+X6FYcVDw4z29yj1FcbJY5E0DDC60QluR7SGXMQ6YfU7MU0WTl'
     'ZxMpcU5tZSDfyEO2mUNCYNACnJKUs+x9RjQfTxk91qV2ubshNJpNzTc6bmcglpdc7xTxi/Et74Zlifdcfa0lYI2T'
     '9bgd0/1AeNQNgZQUPHO7r0bjmjnOlApMMwUlNbakxE/QT9YhopYUmlL4eLLplLsYhgyu9715WLPQudGwac/C7QHY'
     'DyvSTW63N91YsN5GPQGUac6YdnCZq91gGrn4Wd6Xrx73brvTGstSwidziuhBVPT6ZyLPUtqHHCzDyZsseNTzB+TY'
     'bWpH7i4oCehg7408EPhfHb2EyU+OVb2bfGhinKDwGHOl/OfA4sMADag4I9uNDzqAnMav7+d7Cw0AqQMxSU6AOXXF'
     'uYPq9O09MN+t/CFq3qjSEu+fd+Z2g8vYIQZ/TG57IOqMlK+Eu/jeeqC2NvFGTvhy5u61PYOZ9BVWie1gP99xnsS2'
     'xXCm5qEMnegeOSalw1fZxZV+qz6W9dvyayjHv6XIkzQeVF49n4hRHsihxy88/rm3ap3O3Ag8oxzAO0QBHzhPsWKG'
     'Br9zF0Utgt7T4XpcM93d12XDC+sQJLtWpeDWAXvkjSfuF112rsLY30wMkvI+LIVzb5/Ll9D53G4sIF0ASRy96F1Q'
     '7eWQShvFw0mjUxNuEYsv3Sk/B1XGgT/208I0V9Ud4AM='),
    ('multi-block, repeat tables', 300000, '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'
     'ABhFSVYHEADt2sMCCPzHp30ggMB/LNbOBg=='),
    ('repeat offset minus one', 80, '88fb14c0f65b3aa113e2b20007e222ee1b1897e6149661dee844059f63875774',
     'KLUv/SBQzQAAcGJnZ2VlaGFjYWVjY2FjAwA6kfkWYLh4AQ=='),
    ('sparse tail bits', 300, '9dd0f962a43f9c6a46166431232c52d3f79e3cbad9a99fff97103937e9cb5fb2',
     'KLUv/WAsAF0DAEJEDhGAdQ5gq4FNiAnJSpKVERnR6fnrKg9ingtn5F7BMcJNwyhL5Nl8EEiOGZXF7Fg9lBqKcb1c'
     'g/nrBhQgcCKEeu6M4cFcekKRYZw7I6+JYdT+Okg5UJd0IxkTiEIOTH8OgRwOOcYRPCgv'),
]


def zframe(blocks, content=None, checksum=None):
    """Hand-built frame: single-segment header, then (last, type, payload, regen) blocks."""
    fhd = 0x20 | (0x04 if checksum is not None else 0)
    head = struct.pack("<I", zstd_pure.MAGIC) + bytes([fhd, content if content is not None else 0])
    body = b""
    for i, (btype, payload, regen) in enumerate(blocks):
        size = regen if btype == 1 else len(payload)
        body += struct.pack("<I", (size << 3) | (btype << 1) | int(i == len(blocks) - 1))[:3] + payload
    return head + body + (struct.pack("<I", checksum) if checksum is not None else b"")


@pytest.mark.parametrize("name,length,digest,b64", ZSTD_VECTORS)
def test_zstd_pure_reference_vectors(name, length, digest, b64):
    raw = zstd_pure.decompress(base64.b64decode(b64))
    assert len(raw) == length and hashlib.sha256(raw).hexdigest() == digest, name


def test_zstd_pure_handmade_frames():
    # raw block, RLE block, and several blocks in one frame
    assert zstd_pure.decompress(zframe([(0, b"hello", 5)], content=5)) == b"hello"
    assert zstd_pure.decompress(zframe([(1, b"x", 200)], content=200)) == b"x" * 200
    assert zstd_pure.decompress(zframe([(0, b"ab", 2), (1, b"z", 3), (0, b"!", 1)], content=6)) == b"abzzz!"
    # checksum: right value accepted, wrong one refused, and --no-verify style skip works
    good = zstd_pure.xxh64(b"hello") & 0xFFFFFFFF
    assert zstd_pure.decompress(zframe([(0, b"hello", 5)], content=5, checksum=good)) == b"hello"
    with pytest.raises(GstInputError, match="checksum"):
        zstd_pure.decompress(zframe([(0, b"hello", 5)], content=5, checksum=good ^ 1))
    assert zstd_pure.decompress(zframe([(0, b"hello", 5)], content=5, checksum=good ^ 1), verify_checksum=False) == b"hello"
    # concatenated frames and a skippable frame between them
    skip = struct.pack("<II", 0x184D2A55, 3) + b"abc"
    both = zframe([(0, b"one", 3)], content=3) + skip + zframe([(0, b"two", 3)], content=3)
    assert zstd_pure.decompress(both) == b"onetwo"
    # xxh64 against the published test vectors
    assert zstd_pure.xxh64(b"") == 0xEF46DB3751D8E999
    assert zstd_pure.xxh64(b"a") == 0xD24EC4F1A98C6E5B
    assert zstd_pure.xxh64(b"abc") == 0x44BC2CF5AD770999


def test_zstd_pure_direct_weight_huffman_literals():
    """A compressed-literals block whose Huffman tree uses the direct 4-bit weight form (symbols 0..3, 2 bits each)."""
    symbols = [0, 1, 3, 2, 2, 0, 1, 3, 3, 0]
    val = 0
    for s in symbols:
        val = (val << 2) | s                    # codes 00 01 10 11 for symbols 0 1 2 3, first symbol on top
    val |= 1 << (2 * len(symbols))              # end marker
    stream = val.to_bytes((val.bit_length() + 7) // 8, "little")
    tree = bytes([127 + 3, 0x11, 0x10])         # three direct weights (1, 1, 1); the fourth is implied
    comp = len(tree) + len(stream)
    lit_hdr = (2 | (0 << 2) | (len(symbols) << 4) | (comp << 14)).to_bytes(3, "little")
    block = lit_hdr + tree + stream + b"\x00"   # zero sequences
    out = zstd_pure.decompress(zframe([(2, block, len(symbols))], content=len(symbols)))
    assert list(out) == symbols


def test_zstd_pure_typed_errors_and_limits():
    ok = base64.b64decode(ZSTD_VECTORS[0][3])
    bad = {
        "empty": b"",
        "magic": b"\x00\x01\x02\x03\x04\x05",
        "truncated_header": ok[:5],
        "truncated_block": ok[:len(ok) - 6],
        "trailing": ok + b"\x01",
        "reserved_block": zframe([(0, b"", 0)], content=0)[:6] + b"\x07\x00\x00",
        "dictionary": struct.pack("<I", zstd_pure.MAGIC) + bytes([0x21, 0x01, 0x00, 0x00]),
        "content_mismatch": zframe([(0, b"hello", 5)], content=4),
        "skip_truncated": struct.pack("<II", 0x184D2A50, 99) + b"ab",
    }
    for name, raw in bad.items():
        with pytest.raises(GstInputError):
            zstd_pure.decompress(raw)
    # the output limit is enforced for declared sizes and for RLE blocks that outgrow it
    with pytest.raises(GstInputError, match="limit"):
        zstd_pure.decompress(zframe([(1, b"x", 100)], content=100), max_output=50)
    with pytest.raises(GstInputError, match="limit"):
        zstd_pure.decompress(zframe([(1, b"x", 100)], content=None), max_output=50)
    # every single-bit flip and truncation of a real frame is either decoded or a typed error
    for i in range(len(ok) * 8):
        mutated = bytearray(ok)
        mutated[i // 8] ^= 1 << (i % 8)
        try:
            zstd_pure.decompress(bytes(mutated), max_output=1 << 20)
        except GstInputError:
            pass
    for n in range(len(ok)):
        with pytest.raises(GstInputError):
            zstd_pure.decompress(ok[:n])


def test_zstd_in_tile_readers(tmp_path):
    import map_diff, tilemap_stats, tmx_to_json
    gids = [1, 2, 0x80000003, 0, 7, 7]
    raw = struct.pack("<6I", *gids)
    # a frame as the reference library writes it for these bytes (checksum on)
    frame = struct.pack("<IBB", zstd_pure.MAGIC, 0x24, len(raw)) + struct.pack("<I", (len(raw) << 3) | 1)[:3] + raw \
        + struct.pack("<I", zstd_pure.xxh64(raw) & 0xFFFFFFFF)
    b64 = base64.b64encode(frame).decode()
    assert map_diff.decode_tile_data(b64, "base64", "zstd", "L") == gids
    doc = {"type": "map", "width": 3, "height": 2, "tilewidth": 8, "tileheight": 8, "tilesets": [],
           "layers": [{"type": "tilelayer", "name": "g", "width": 3, "height": 2, "encoding": "base64",
                       "compression": "zstd", "data": b64}]}
    src = tmp_path / "z.json"
    src.write_text(json.dumps(doc))
    assert tilemap_stats.main([str(src), "--json", str(tmp_path / "s.json")]) == 0
    tmx = tmp_path / "z.tmx"
    tmx.write_text('<map version="1.10" orientation="orthogonal" width="3" height="2" tilewidth="8" tileheight="8">'
                   '<layer id="1" name="g" width="3" height="2"><data encoding="base64" compression="zstd">%s</data></layer></map>' % b64)
    assert tmx_to_json.convert(str(tmx))["layers"][0]["data"] == gids
    with pytest.raises(GstInputError, match="layer 'L'.*zstd"):
        map_diff.decode_tile_data(base64.b64encode(frame[:-9]).decode(), "base64", "zstd", "L")


def test_zstd_pure_mutation_fuzz():
    """Seeded mutations of every reference frame decode or raise GstInputError; nothing else escapes, nothing hangs."""
    import random, time
    rng = random.Random(1234)
    frames = [base64.b64decode(v[3]) for v in ZSTD_VECTORS]
    started = time.time()
    for _ in range(1500):
        data = bytearray(rng.choice(frames))
        kind = rng.randrange(4)
        if kind == 0:
            for _ in range(rng.choice((1, 2, 4))):
                data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        elif kind == 1:
            del data[rng.randrange(len(data)):]
        elif kind == 2:
            for _ in range(rng.choice((1, 3, 6))):
                data[rng.randrange(len(data))] = rng.randrange(256)
        else:
            at = rng.randrange(len(data))
            data[at:at + rng.randrange(1, 12)] = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 12)))
        try:
            zstd_pure.decompress(bytes(data), max_output=2 << 20, verify_checksum=bool(rng.getrandbits(1)))
        except GstInputError:
            pass
    assert time.time() - started < 60
