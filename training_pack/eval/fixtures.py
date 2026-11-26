"""Eval fixtures, written from scratch (PIL, wave, json). Nothing here imports kit code."""
import json, math, os, struct, wave
from PIL import Image

PICO8 = ["000000", "1d2b53", "7e2553", "008751", "ab5236", "5f574f", "c2c3c7", "fff1e8",
         "ff004d", "ffa300", "ffec27", "00e436", "29adff", "83769c", "ff77a8", "ffccaa"]


def _sprite(w=16, h=16, box=(4, 4, 12, 12), rgb=(255, 0, 77)):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            im.putpixel((x, y), rgb + (255,))
    return im


def write_wav(path, seconds=0.5, rate=44100, channels=1, freq=440.0, amp=0.5, lead=0.0, tail=0.0):
    n_lead, n, n_tail = int(lead * rate), int(seconds * rate), int(tail * rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate)
        frames = bytearray()
        for i in range(n_lead + n + n_tail):
            v = 0
            if n_lead <= i < n_lead + n:
                v = int(amp * 32767 * math.sin(2 * math.pi * freq * (i - n_lead) / rate))
            for c in range(channels):
                frames += struct.pack("<h", v if c == 0 else v // 2)
        w.writeframes(bytes(frames))


def tiled_map(w=10, h=8):
    ground = [1] * (w * h)
    walls = [2 if (x in (0, w - 1) or y in (0, h - 1)) else 0 for y in range(h) for x in range(w)]
    return {"width": w, "height": h, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal",
            "renderorder": "right-down", "type": "map", "version": "1.10", "tiledversion": "1.10.2",
            "infinite": False, "nextlayerid": 4, "nextobjectid": 3,
            "tilesets": [{"firstgid": 1, "name": "tiles", "image": "tiles.png", "imagewidth": 32, "imageheight": 16,
                          "tilewidth": 16, "tileheight": 16, "tilecount": 2, "columns": 2, "margin": 0, "spacing": 0}],
            "layers": [
                {"id": 1, "name": "ground", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
                 "opacity": 1, "visible": True, "data": ground},
                {"id": 2, "name": "walls", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
                 "opacity": 1, "visible": True, "data": walls},
                {"id": 3, "name": "objects", "type": "objectgroup", "x": 0, "y": 0, "opacity": 1, "visible": True,
                 "draworder": "topdown", "objects": [
                     {"id": 1, "name": "spawn", "type": "spawn", "x": 2 * 16 + 8, "y": 2 * 16 + 8, "width": 0, "height": 0,
                      "rotation": 0, "visible": True, "point": True},
                     {"id": 2, "name": "goal", "type": "goal", "x": 7 * 16 + 8, "y": 5 * 16 + 8, "width": 0, "height": 0,
                      "rotation": 0, "visible": True, "point": True}]}]}


TMX = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" tiledversion="1.10.2" orientation="orthogonal" renderorder="right-down" width="4" height="3"
 tilewidth="16" tileheight="16" infinite="0" nextlayerid="2" nextobjectid="1">
 <tileset firstgid="1" name="tiles" tilewidth="16" tileheight="16" tilecount="2" columns="2">
  <image source="tiles.png" width="32" height="16"/>
 </tileset>
 <layer id="1" name="ground" width="4" height="3">
  <data encoding="csv">
1,1,1,1,
1,2,2,1,
1,1,1,1
</data>
 </layer>
</map>
"""

CUBE_OBJ = """# unit cube, 8 verts, 6 quads
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""

LOC_CSV = "id,en,de\nmenu_start,Start,Starten\nmenu_quit,Quit,Beenden\nhud_coins,Coins: {n},Münzen: {n}\n"
LOC_CSV_BAD = "id,en,de\nmenu_start,Start,Starten\nhud_coins,Coins: {n},Münzen\n"
LOC_CSV_B = "id,en,de\nmenu_options,Options,Optionen\n"


def build(d, kit_root):
    os.makedirs(d, exist_ok=True)
    j = lambda *p: os.path.join(d, *p)
    os.makedirs(j("frames"), exist_ok=True)
    for i in range(4):                                   # walk_0..3: 16x16 canvas, 8x8 opaque box shifting right
        _sprite(box=(2 + i, 4, 10 + i, 12)).save(j("frames", "walk_%d.png" % i))
    for i in range(2):
        _sprite(rgb=(41, 173, 255)).save(j("frames", "idle_%d.png" % i))
    _sprite().save(j("sprite.png"))
    px = Image.new("RGBA", (16, 16), (0, 0, 0, 0))        # 1-px outline box + inner line, 2 colours, no orphans
    for i in range(2, 13):
        for x, y in ((i, 3), (i, 13), (2, i + 1), (12, i + 1)):
            px.putpixel((x, y), (29, 43, 83, 255))
    for x in range(3, 12):
        px.putpixel((x, 7), (255, 0, 77, 255))
    px.save(j("pixel.png"))
    sheet = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for i in range(4):
        sheet.paste(_sprite(box=(2 + i, 4, 10 + i, 12)), (16 * i, 0))
    sheet.save(j("sheet.png"))
    tiles = Image.new("RGBA", (32, 16), (200, 196, 180, 255)); tiles.paste((52, 48, 64, 255), (16, 0, 32, 16))
    tiles.save(j("tiles.png"))
    dup = Image.new("RGBA", (48, 16), (200, 196, 180, 255)); dup.paste((52, 48, 64, 255), (16, 0, 32, 16))
    dup.save(j("tiles_dup.png"))                         # tiles 0 and 2 identical
    Image.new("RGBA", (20, 12), (10, 120, 200, 255)).save(j("odd.png"))
    grad = Image.new("RGB", (32, 32))
    for x in range(32):
        for y in range(32):
            grad.putpixel((x, y), (x * 8, y * 8, 128))
    grad.save(j("grad.png"))
    Image.new("L", (16, 16), 200).save(j("ao.png")); Image.new("L", (16, 16), 100).save(j("rough.png"))
    Image.new("L", (16, 16), 0).save(j("metal.png"))
    h = Image.new("L", (32, 32))
    for x in range(32):
        for y in range(32):
            h.putpixel((x, y), int(127 + 120 * math.sin(x / 5.0)))
    h.save(j("height.png"))
    gif = [_sprite(box=(2 + 3 * i, 4, 8 + 3 * i, 12)) for i in range(3)]
    gif[0].save(j("anim.gif"), save_all=True, append_images=gif[1:], duration=100, loop=0, disposal=2)
    write_wav(j("tone.wav"))
    write_wav(j("tone_stereo.wav"), channels=2)
    write_wav(j("padded.wav"), seconds=0.3, lead=0.25, tail=0.25)
    write_wav(j("quiet.wav"), amp=0.05)
    json.dump(tiled_map(), open(j("map.json"), "w"))
    open(j("map.tmx"), "w").write(TMX)
    open(j("cube.obj"), "w").write(CUBE_OBJ)
    open(j("loc.csv"), "w", encoding="utf-8").write(LOC_CSV)
    open(j("loc_bad.csv"), "w", encoding="utf-8").write(LOC_CSV_BAD)
    open(j("loc_b.csv"), "w", encoding="utf-8").write(LOC_CSV_B)
    open(j("pico8.hex"), "w").write("\n".join(PICO8) + "\n")
    open(j("enemies.csv"), "w").write("id,name,hp,speed\nbat,Bat,2,40\nslime,Slime,3,20\n")
    # tiny Godot project: main scene -> art/hero.png; art/orphan.png referenced by nothing
    p = j("proj"); os.makedirs(os.path.join(p, "art"), exist_ok=True)
    open(os.path.join(p, "project.godot"), "w").write(
        'config_version=5\n[application]\nconfig/name="Eval"\nrun/main_scene="res://main.tscn"\n'
        '[input]\nmove_left={"deadzone": 0.5, "events": []}\n')
    open(os.path.join(p, "main.tscn"), "w").write(
        '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Texture2D" path="res://art/hero.png" id="1"]\n\n'
        '[node name="Main" type="Node2D"]\n\n[node name="Hero" type="Sprite2D" parent="."]\ntexture = ExtResource("1")\n')
    _sprite().save(os.path.join(p, "art", "hero.png")); _sprite().save(os.path.join(p, "art", "orphan.png"))
    pb = j("proj_broken"); os.makedirs(pb, exist_ok=True)
    open(os.path.join(pb, "project.godot"), "w").write('config_version=5\n[application]\nrun/main_scene="res://main.tscn"\n')
    open(os.path.join(pb, "main.tscn"), "w").write(
        '[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Texture2D" path="res://art/missing.png" id="1"]\n\n'
        '[node name="Main" type="Node2D"]\n')
    font = os.path.join(kit_root, "examples", "sample-topdown", "data", "fonts", "DejaVuSans.ttf")
    if os.path.isfile(font):
        os.symlink(font, j("font.ttf"))
    open(j("chars.txt"), "w").write("ABCabc0123")
