#!/usr/bin/env python3
"""Deterministic temp-project fixture for trajectory generation.

Nothing here imports kit code or talks to the network. The same function
rebuilds the same files, so a stored trajectory can be re-run and checked.
"""
import json, math, os, shutil, struct, wave
from PIL import Image

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PICO8 = ["000000", "1d2b53", "7e2553", "008751", "ab5236", "5f574f", "c2c3c7", "fff1e8",
         "ff004d", "ffa300", "ffec27", "00e436", "29adff", "83769c", "ff77a8", "ffccaa"]


def _rgba(w, h, rgb, box=None):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x0, y0, x1, y1 = box or (0, 0, w, h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            im.putpixel((x, y), rgb + (255,))
    return im


def _save(im, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)


def write_wav(path, seconds=0.25, rate=22050, channels=1, freq=440.0, amp=0.5, lead=0.0, tail=0.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n_lead, n, n_tail = int(lead * rate), int(seconds * rate), int(tail * rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n_lead + n + n_tail):
            v = 0
            if n_lead <= i < n_lead + n:
                v = int(amp * 32767 * math.sin(2 * math.pi * freq * (i - n_lead) / rate))
            for c in range(channels):
                frames += struct.pack("<h", v if c == 0 else int(v * 0.6))
        w.writeframes(bytes(frames))


def tiled_map(w=10, h=8, objects=None, tile="tiles.png"):
    ground = [1] * (w * h)
    walls = [2 if (x in (0, w - 1) or y in (0, h - 1)) else 0 for y in range(h) for x in range(w)]
    objects = objects if objects is not None else [
        {"id": 1, "name": "spawn", "type": "spawn", "x": 32, "y": 32, "width": 0, "height": 0,
         "rotation": 0, "visible": True, "point": True},
        {"id": 2, "name": "goal", "type": "goal", "x": 112, "y": 80, "width": 0, "height": 0,
         "rotation": 0, "visible": True, "point": True},
    ]
    return {
        "width": w, "height": h, "tilewidth": 16, "tileheight": 16,
        "orientation": "orthogonal", "renderorder": "right-down", "type": "map",
        "version": "1.10", "tiledversion": "1.10.2", "infinite": False,
        "nextlayerid": 4, "nextobjectid": 1 + len(objects),
        "tilesets": [{
            "firstgid": 1, "name": "tiles", "image": tile,
            "imagewidth": 32, "imageheight": 16, "tilewidth": 16, "tileheight": 16,
            "tilecount": 2, "columns": 2, "margin": 0, "spacing": 0,
        }],
        "layers": [
            {"id": 1, "name": "ground", "type": "tilelayer", "width": w, "height": h,
             "opacity": 1, "visible": True, "data": ground},
            {"id": 2, "name": "walls", "type": "tilelayer", "width": w, "height": h,
             "opacity": 1, "visible": True, "data": walls},
            {"id": 3, "name": "objects", "type": "objectgroup", "opacity": 1, "visible": True,
             "draworder": "topdown", "objects": objects},
        ],
    }


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")


def _text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build(root, kit=None):
    """Create a small game project under root. Idempotent for a fresh directory."""
    kit = kit or KIT
    os.makedirs(root, exist_ok=True)
    j = lambda *p: os.path.join(root, *p)

    # sprites: walk cycle shifts an 8x8 body across a 16x16 canvas
    for i in range(4):
        _save(_rgba(16, 16, (255, 0, 77), (2 + i, 4, 10 + i, 12)), j("sprites", "walk_%d.png" % i))
        _save(_rgba(16, 16, (255, 0, 77), (2 + i, 4, 10 + i, 12)), j("godot", "sprites", "walk_%d.png" % i))
    for i in range(2):
        _save(_rgba(16, 16, (41, 173, 255), (4, 4, 12, 12)), j("sprites", "idle_%d.png" % i))
        _save(_rgba(16, 16, (41, 173, 255), (4, 4, 12, 12)), j("godot", "sprites", "idle_%d.png" % i))
    hero = _rgba(16, 16, (255, 0, 77), (4, 4, 12, 12))
    _save(hero, j("sprites", "hero.png"))
    _save(hero, j("godot", "art", "hero.png"))
    _save(_rgba(16, 16, (255, 163, 0), (5, 5, 11, 11)), j("godot", "art", "orphan.png"))
    _save(_rgba(16, 16, (255, 236, 39), (3, 3, 13, 13)), j("sprites", "coin.png"))
    _save(_rgba(16, 16, (0, 228, 54), (2, 6, 14, 14)), j("sprites", "slime.png"))
    # ui panel with alpha (asset-lint ui rule)
    panel = Image.new("RGBA", (32, 16), (29, 43, 83, 255))
    for x in range(32):
        panel.putpixel((x, 0), (194, 195, 199, 255))
        panel.putpixel((x, 15), (194, 195, 199, 255))
    _save(panel, j("godot", "ui", "panel.png"))

    sheet = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for i in range(4):
        sheet.paste(_rgba(16, 16, (255, 0, 77), (2 + i, 4, 10 + i, 12)), (16 * i, 0))
    _save(sheet, j("sheets", "walk.png"))

    # dotted layer names for sprite-stack
    _save(_rgba(16, 16, (0, 0, 0), (4, 12, 12, 15)), j("sprites", "stack", "hero.shadow.png"))
    _save(_rgba(16, 16, (255, 0, 77), (4, 4, 12, 12)), j("sprites", "stack", "hero.body.png"))
    _save(_rgba(16, 16, (29, 43, 83), (3, 3, 13, 13)), j("sprites", "stack", "hero.outline.png"))

    tiles = Image.new("RGBA", (32, 16), (74, 143, 60, 255))
    tiles.paste((90, 78, 64, 255), (16, 0, 32, 16))
    _save(tiles, j("maps", "tiles.png"))
    _save(tiles, j("tiles", "tiles.png"))
    dup = Image.new("RGBA", (48, 16), (74, 143, 60, 255))
    dup.paste((90, 78, 64, 255), (16, 0, 32, 16))
    _save(dup, j("tiles", "tiles_dup.png"))  # tile 0 == tile 2

    # 3x3 autotile template, 16 px cells
    tpl = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    colours = [(74, 143, 60), (138, 106, 63), (41, 173, 255),
               (255, 163, 0), (255, 0, 77), (255, 236, 39),
               (126, 37, 83), (0, 135, 81), (194, 195, 199)]
    for i, rgb in enumerate(colours):
        tpl.paste(rgb + (255,), ((i % 3) * 16, (i // 3) * 16, (i % 3) * 16 + 16, (i // 3) * 16 + 16))
    _save(tpl, j("tiles", "template3x3.png"))

    # textures
    grad = Image.new("RGB", (32, 32))
    for y in range(32):
        for x in range(32):
            grad.putpixel((x, y), (x * 8, y * 8, 140))
    _save(grad, j("textures", "grad.png"))
    _save(Image.new("RGBA", (20, 12), (10, 120, 200, 255)), j("textures", "odd.png"))
    _save(Image.new("L", (16, 16), 200), j("textures", "ao.png"))
    _save(Image.new("L", (16, 16), 100), j("textures", "rough.png"))
    _save(Image.new("L", (16, 16), 0), j("textures", "metal.png"))
    _save(Image.new("RGB", (16, 16), (128, 128, 255)), j("textures", "flat_normal.png"))
    h = Image.new("L", (32, 32))
    for y in range(32):
        for x in range(32):
            h.putpixel((x, y), int(127 + 100 * math.sin(x / 4.0) * math.cos(y / 5.0)))
    _save(h, j("textures", "height.png"))
    _save(Image.new("RGB", (32, 16), (70, 140, 210)), j("textures", "sky.png"))
    _save(Image.new("RGB", (32, 16), (40, 90, 40)), j("textures", "hills.png"))
    for name, rgb in (("px", (220, 80, 80)), ("nx", (80, 80, 220)), ("py", (220, 220, 80)),
                      ("ny", (80, 180, 80)), ("pz", (180, 80, 180)), ("nz", (80, 180, 180))):
        _save(Image.new("RGB", (16, 16), rgb), j("textures", "faces", "%s.png" % name))
    # pixel-art mark: 1 px features, two colours
    px = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for i in range(2, 14):
        px.putpixel((i, 2), (29, 43, 83, 255))
        px.putpixel((i, 13), (29, 43, 83, 255))
        px.putpixel((2, i), (29, 43, 83, 255))
        px.putpixel((13, i), (29, 43, 83, 255))
    px.putpixel((8, 8), (255, 0, 77, 255))
    _save(px, j("textures", "pixel.png"))

    gif_frames = [_rgba(16, 16, (255, 0, 77), (2 + 3 * i, 4, 8 + 3 * i, 12)) for i in range(3)]
    os.makedirs(j("sheets"), exist_ok=True)
    gif_frames[0].save(j("sheets", "anim.gif"), save_all=True, append_images=gif_frames[1:],
                       duration=100, loop=0, disposal=2)

    # audio at 22050 so steps stay small
    write_wav(j("audio", "tone.wav"), seconds=0.25, freq=440)
    write_wav(j("audio", "quiet.wav"), seconds=0.25, freq=440, amp=0.05)
    write_wav(j("audio", "stereo.wav"), seconds=0.25, freq=440, channels=2)
    write_wav(j("audio", "padded.wav"), seconds=0.2, freq=330, lead=0.1, tail=0.1)
    write_wav(j("audio", "blip.wav"), seconds=0.1, freq=880, amp=0.4)
    # lines for subtitle timing, named by id
    write_wav(j("audio", "vo", "line_hello.wav"), seconds=0.4, freq=220, amp=0.3)

    # maps
    _dump(j("maps", "level.json"), tiled_map())
    town_door = [
        {"id": 1, "name": "spawn", "type": "spawn", "x": 24, "y": 24, "width": 0, "height": 0, "point": True, "visible": True},
        {"id": 2, "name": "to_shop", "type": "door", "x": 64, "y": 32, "width": 16, "height": 16, "visible": True,
         "properties": [{"name": "target", "type": "string", "value": "shop"}]},
    ]
    _dump(j("maps", "town.json"), tiled_map(8, 6, town_door))
    _dump(j("maps", "shop.json"), tiled_map(6, 6, [
        {"id": 1, "name": "spawn", "type": "spawn", "x": 24, "y": 24, "width": 0, "height": 0, "point": True, "visible": True},
    ]))
    _text(j("maps", "level.tmx"), """<?xml version="1.0" encoding="UTF-8"?>
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
""")
    _text(j("maps", "wfc_example.csv"), "0,1,0,1\n1,0,1,0\n0,1,0,1\n1,0,1,0\n")
    _dump(j("maps", "infinite.json"), {
        "type": "map", "orientation": "orthogonal", "infinite": True,
        "tilewidth": 16, "tileheight": 16, "width": 1, "height": 1,
        "tilesets": [{"firstgid": 1, "name": "tiles", "image": "tiles.png",
                      "tilewidth": 16, "tileheight": 16, "tilecount": 2, "columns": 2}],
        "layers": [{"id": 1, "name": "ground", "type": "tilelayer",
                    "chunks": [{"x": 0, "y": 0, "width": 2, "height": 2, "data": [1, 1, 1, 2]}]}],
    })
    _dump(j("maps", "floor_rules.json"), {
        "source": "ground", "name": "decor", "match": "gid",
        "rules": [{"center": [1], "gid": 1}, {"gid": 2}],
    })
    _dump(j("maps", "remap.json"), {"1": 2, "2": 1})
    _dump(j("maps", "level_budget.json"), {
        "count": "type",
        "defaults": {"spawn": 4, "goal": 4, "door": 4},
        "ignore": [],
    })
    _dump(j("maps", "props.schema.json"), {
        "objects": {
            "spawn": {"required": [], "types": {}},
            "goal": {"required": [], "types": {}},
            "door": {"required": ["target"], "types": {"target": "string"}},
        },
    })
    tileset = {
        "type": "tileset", "name": "ground", "tilewidth": 16, "tileheight": 16,
        "tilecount": 2, "columns": 2, "margin": 0, "spacing": 0,
        "image": "tiles.png", "imagewidth": 32, "imageheight": 16,
        "tiles": [{"id": 0, "animation": [
            {"tileid": 0, "duration": 200}, {"tileid": 1, "duration": 200}]}],
    }
    _dump(j("maps", "ground.tsj"), tileset)
    other = dict(tileset)
    other["name"] = "accent"
    other["image"] = "tiles.png"
    _dump(j("tiles", "accent.tsj"), other)
    # accent image lives next to the tsj
    _save(tiles, j("tiles", "tiles.png"))

    # meshes
    _text(j("mesh", "crate.obj"), """# unit cube, 6 quads
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
""")
    _text(j("mesh", "prop.obj"), """# two groups, triangles, uvs
vt 0 0
vt 1 0
vt 1 1
vt 0 1
v 0 0 0
v 1 0 0
v 1 0 1
v 0 0 1
g body
f 1/1 2/2 3/3
f 1/1 3/3 4/4
v 0 0.2 0
v 1 0.2 0
v 0.5 0.2 1
g lid
f 5/1 6/2 7/3
""")
    _text(j("mesh", "wedge.obj"), """v 0 0 0
v 1 0 0
v 0 1 0
vt 0 0
vt 1 0
vt 0 1
f 1/1 2/2 3/3
""")
    _text(j("mesh", "lid.obj"), """v 0 0 0
v 1 0 0
v 0 1 0
f 1 2 3
""")

    # loc / dialogue / data
    _text(j("loc", "strings.csv"), "id,en,de\nmenu_start,Start,Starten\nmenu_quit,Quit,Beenden\nhud_coins,Coins: {n},Münzen: {n}\n")
    _text(j("loc", "strings_b.csv"), "id,en,de\nmenu_options,Options,Optionen\nhud_coins,Coins: {n},Muenzen: {n}\n")
    _text(j("loc", "strings_gap.csv"), "id,en,de\nmenu_start,Start,\nmenu_quit,Quit,Beenden\n")
    _text(j("loc", "strings_bad.csv"), "id,en,de\nmenu_start,Start,Starten\nhud_coins,Coins: {n},Münzen\n")
    _text(j("loc", "plurals.csv"),
          'id,en\nitem_count,"{count, plural, one {# coin} other {# coins}}"\n')
    _text(j("loc", "rename_map.csv"), "old,new\nmenu_start,ui_start\n")
    _text(j("dialogue", "intro.yarn"),
          "title: Start\n---\nAva: The gate is shut.\n-> Open it\n    <<jump Open>>\n===\n"
          "title: Open\n---\nAva: It opens.\n===\n")
    _text(j("dialogue", "intro.ink"),
          "The road splits.\n* [Left] -> left\n* [Right] -> right\n== left ==\nA quiet lane.\n-> END\n"
          "== right ==\nA busy street.\n-> END\n")
    _text(j("dialogue", "lines.csv"), "id,text,speaker\nline_hello,The gate is shut.,Ava\n")
    _text(j("data", "items.csv"), "id,name,price,rarity\npotion,Potion,5,common\nsword,Sword,20,rare\n")
    _text(j("data", "items_b.csv"), "id,name,price,rarity\npotion,Potion,6,common\nshield,Shield,15,common\n")
    _text(j("data", "enemies.csv"), "id,name,hp,speed\nbat,Bat,2,40\nslime,Slime,3,20\n")
    _dump(j("data", "schema.json"), {"tables": {"items": {"file": "items.csv", "key": "id", "fields": {
        "id": {"type": "str", "unique": True},
        "name": {"type": "str"},
        "price": {"type": "int", "min": 0},
        "rarity": {"type": "enum", "values": ["common", "rare"]},
    }}}})
    _dump(j("data", "loot.json"), {"tables": {"chest": {"entries": [
        {"item": "potion", "weight": 3}, {"item": "sword", "weight": 1}]}}})
    _text(j("data", "prompts.csv"), "name,subject,seed\ncoin,gold coin icon,1\nslime,green slime sprite,2\n")
    _text(j("data", "cues.csv"), "cue,mood,bpm,length_s,loop\ntown,calm village,90,8,yes\n")
    _text(j("data", "shots.csv"), "shot,prompt,seconds,seed\nintro,hero at a stone gate,2,3\n")
    _dump(j("data", "mix.json"), {
        "sample_rate": 22050, "channels": 1, "normalize": True, "peak_db": -1.0, "tail_ms": 20,
        "layers": [{"file": "../audio/tone.wav", "offset_ms": 0}, {"file": "../audio/blip.wav", "offset_ms": 80}],
    })
    _dump(j("data", "input_map.json"), {"actions": {
        "move_left": ["Key:A", "Pad:button14"],
        "jump": ["Key:Space", "Pad:button0"],
    }})
    _text(j("data", "credits.txt"), "# Meadow Gate\n\nAva the Warden\n\nTools\n\ngamestudio-tools\n")
    _text(j("data", "chars.txt"), "ABCabc0123 Start\n")
    _text(j("fonts", "extra.txt"), "StartQuit\n")

    # aseprite JSON + sheet, and a binary seed copied from the kit's fuzz fixtures
    ase_sheet = Image.new("RGBA", (16, 4), (0, 0, 0, 0))
    for i, rgb in enumerate(((255, 0, 77), (41, 173, 255), (0, 228, 54), (255, 163, 0))):
        ase_sheet.paste(rgb + (255,), (i * 4, 0, i * 4 + 4, 4))
    _save(ase_sheet, j("anim", "seed.png"))
    frames = [{"filename": "f%d" % i, "frame": {"x": i * 4, "y": 0, "w": 4, "h": 4}, "rotated": False,
               "trimmed": False, "spriteSourceSize": {"x": 0, "y": 0, "w": 4, "h": 4},
               "sourceSize": {"w": 4, "h": 4}, "duration": 100} for i in range(4)]
    _dump(j("anim", "sheet.json"), {"frames": frames, "meta": {
        "image": "seed.png", "size": {"w": 16, "h": 4},
        "frameTags": [{"name": "idle", "from": 0, "to": 1, "direction": "forward"},
                      {"name": "run", "from": 0, "to": 3, "direction": "forward"}]}})
    src_ase = os.path.join(kit, "tests", "fuzz", "seeds", "seed.ase")
    if os.path.isfile(src_ase):
        os.makedirs(j("anim"), exist_ok=True)
        shutil.copyfile(src_ase, j("anim", "seed.ase"))

    font = os.path.join(kit, "examples", "sample-topdown", "data", "fonts", "DejaVuSans.ttf")
    if os.path.isfile(font):
        os.makedirs(j("fonts"), exist_ok=True)
        shutil.copyfile(font, j("fonts", "DejaVuSans.ttf"))

    _text(j("godot", "project.godot"), """config_version=5

[application]
config/name="MeadowGate"
run/main_scene="res://main.tscn"

[input]

move_left={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":65,"key_label":0,"unicode":97,"location":0,"echo":false,"script":null)
]
}
jump={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":32,"key_label":0,"unicode":32,"location":0,"echo":false,"script":null)
]
}
""")
    _text(j("godot", "main.tscn"), """[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://art/hero.png" id="1"]

[node name="Main" type="Node2D"]

[node name="Hero" type="Sprite2D" parent="."]
texture = ExtResource("1")
""")
    _dump(j("godot", "import_rules.json"), {"rules": [
        {"glob": "art/*.png", "preset": "pixel"},
        {"glob": "ui/*.png", "preset": "ui"},
        {"glob": "sprites/*.png", "preset": "pixel"},
    ]})
    _text(j("godot", "player.gd"),
          "extends Node2D\n\nfunc _physics_process(_delta):\n"
          "\tif Input.is_action_pressed(\"move_left\"):\n\t\tposition.x -= 1\n"
          "\tif Input.is_action_just_pressed(\"jump\"):\n\t\tposition.y -= 4\n")
    os.makedirs(j("build"), exist_ok=True)
    os.makedirs(j("variants"), exist_ok=True)
    os.makedirs(j("out"), exist_ok=True)
    return root
