"""Stdlib-only writers for tiny valid seeds used by the fuzz harness.

No Pillow, no numpy, no kit imports. Generated files live under tests/fuzz/seeds/
(or a caller-supplied directory).
"""
from __future__ import annotations

import json, os, struct, zlib

KINDS = ("wav", "png", "gif", "tiled", "tmx", "glb", "gltf", "obj",
         "atlas", "loc", "yarn", "ink", "fnt", "fntxml", "fntbin", "colliders", "tiledzstd", "tmxzstd", "ase",
         "tsx", "tiledanim", "tmxext", "asejson")


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path, w=4, h=4, rgba=None):
    if rgba is None:
        rgba = bytes([255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 0, 255] * ((w * h + 3) // 4))[: w * h * 4]
    rows = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(rows, 9)) + _chunk(b"IEND", b"")
    open(path, "wb").write(data)
    return path


def write_gif(path, w=2, h=2):
    # 2x2, 2-color, no animation, global palette
    # Header + LSD + GCT + image descriptor + lzw + trailer
    # This is a well-known minimal 2x2 GIF87a.
    pal = b"\xff\x00\x00\x00\xff\x00"  # 2 colors (flag says 2, size 0 => 2 entries)
    # Logical Screen: w,h, packed (GCT=1, res=0, sort=0, size=0), bg=0, aspect=0
    lsd = struct.pack("<HHBBB", w, h, 0x80, 0, 0)
    # Image descriptor: sep, x,y,w,h, packed
    img = b"\x2c" + struct.pack("<HHHHB", 0, 0, w, h, 0)
    # LZW min code size 2, then a tiny sub-block. 4 pixels of color 0.
    # codes: clear(4), 0,0,0,0, eoi(5) — encoded loosely; use a known-good blob.
    # A widely used 1x1 gif:
    one = (b"GIF89a"
           + struct.pack("<HH", 1, 1)
           + b"\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00"
           + struct.pack("<HH", 1, 1)
           + b"\x00\x02\x02D\x01\x00;")
    open(path, "wb").write(one if (w, h) == (1, 1) else (
        b"GIF89a" + lsd + pal + b"!\xf9\x04\x01\x00\x00\x00\x00" + img
        + b"\x02\x02\x4c\x01\x00;"
    ))
    return path


def write_wav(path, frames=64, sr=8000, ch=1, bits=16):
    nch, bps = ch, bits
    block = nch * bps // 8
    data = b"\x00\x10" * (frames * nch) if bits == 16 else b"\x00" * (frames * block)
    byte_rate = sr * block
    fmt = struct.pack("<HHIIHH", 1, nch, sr, byte_rate, block, bps)
    riff_size = 4 + (8 + len(fmt)) + (8 + len(data))
    blob = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"
    blob += b"fmt " + struct.pack("<I", len(fmt)) + fmt
    blob += b"data" + struct.pack("<I", len(data)) + data
    open(path, "wb").write(blob)
    return path


def write_tiled(path, w=4, h=3, tw=8, th=8):
    data = [1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1][: w * h]
    while len(data) < w * h:
        data.append(0)
    rec = {
        "type": "map", "width": w, "height": h, "tilewidth": tw, "tileheight": th,
        "orientation": "orthogonal", "renderorder": "right-down", "infinite": False,
        "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4, "columns": 2,
                      "image": "tiles.png", "imagewidth": 16, "imageheight": 16,
                      "tilewidth": tw, "tileheight": th}],
        "layers": [{"type": "tilelayer", "name": "ground", "width": w, "height": h, "data": data, "visible": True},
                   {"type": "objectgroup", "name": "things", "objects": [
                       {"id": 1, "name": "tree", "gid": 2 | 0x80000000, "x": 8, "y": 16, "width": tw, "height": th},
                       {"id": 2, "name": "spin", "gid": 3 | 0x20000000, "x": 16, "y": 16, "width": tw, "height": th,
                        "rotation": 45},
                       {"id": 3, "name": "zone", "x": 0, "y": 0, "width": 8, "height": 8},
                       {"id": 4, "name": "poly", "x": 8, "y": 8, "polygon": [{"x": 0, "y": 0}, {"x": 8, "y": 0}, {"x": 4, "y": 8}]},
                       {"id": 5, "name": "mark", "x": 4, "y": 4, "point": True}]}],
    }
    json.dump(rec, open(path, "w"), indent=2)
    return path


def write_tmx(path, w=4, h=3, tw=8, th=8):
    data = ",".join("1" if i % 5 else "0" for i in range(w * h))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<map version="1.10" tiledversion="1.10.0" orientation="orthogonal" '
        'renderorder="right-down" width="%d" height="%d" tilewidth="%d" tileheight="%d" infinite="0">\n'
        ' <tileset firstgid="1" name="t" tilewidth="%d" tileheight="%d" tilecount="4" columns="2">\n'
        '  <image source="tiles.png" width="16" height="16"/>\n'
        ' </tileset>\n'
        ' <layer id="1" name="ground" width="%d" height="%d">\n'
        '  <data encoding="csv">\n%s\n  </data>\n'
        ' </layer>\n'
        '</map>\n'
    ) % (w, h, tw, th, tw, th, w, h, data)
    open(path, "w", encoding="utf-8").write(xml)
    return path


def write_obj(path):
    open(path, "w", encoding="utf-8").write(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nvn 0 0 1\nf 1/1/1 2/2/1 3/3/1\n"
    )
    return path


def write_gltf(path, bin_name=None):
    # 3 vertices, tight
    positions = struct.pack("<fffffffff", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    rec = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "mode": 4}]}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "max": [1, 1, 0], "min": [0, 0, 0]}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962}],
        "buffers": [{"byteLength": 36}],
    }
    if bin_name:
        rec["buffers"][0]["uri"] = bin_name
        open(os.path.join(os.path.dirname(path) or ".", bin_name), "wb").write(positions)
    else:
        # embed as data uri so a lone .gltf is valid
        import base64
        rec["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(positions).decode("ascii")
    json.dump(rec, open(path, "w"))
    return path


def write_glb(path):
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "mode": 4}]}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                       "max": [1, 1, 0], "min": [0, 0, 0]}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962}],
        "buffers": [{"byteLength": 36}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - (len(js) % 4)) % 4)
    bin_ = struct.pack("<fffffffff", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    bin_ += b"\x00" * ((4 - (len(bin_) % 4)) % 4)
    length = 12 + 8 + len(js) + 8 + len(bin_)
    blob = b"glTF" + struct.pack("<II", 2, length)
    blob += struct.pack("<II", len(js), 0x4E4F534A) + js  # JSON
    blob += struct.pack("<II", len(bin_), 0x004E4942) + bin_  # BIN
    open(path, "wb").write(blob)
    return path


def write_atlas(dirpath, base="atlas"):
    os.makedirs(dirpath, exist_ok=True)
    png = os.path.join(dirpath, base + ".png")
    write_png(png, 8, 4)
    rec = {
        "frames": {
            "a.png": {
                "frame": {"x": 0, "y": 0, "w": 4, "h": 4},
                "rotated": False, "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 4, "h": 4},
                "sourceSize": {"w": 4, "h": 4},
            },
            "b.png": {
                "frame": {"x": 4, "y": 0, "w": 4, "h": 4},
                "rotated": False, "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": 4, "h": 4},
                "sourceSize": {"w": 4, "h": 4},
            },
        },
        "meta": {"image": base + ".png", "size": {"w": 8, "h": 4}, "format": "RGBA8888", "scale": "1"},
    }
    jp = os.path.join(dirpath, base + ".json")
    json.dump(rec, open(jp, "w"), indent=2)
    return jp, png


def write_loc(path):
    open(path, "w", encoding="utf-8").write("id,en,fr\nui.hello,Hello,Bonjour\nui.bye,Bye,\n")
    return path


def write_yarn(path):
    open(path, "w", encoding="utf-8").write(
        "title: Start\n---\nAlice: Hello there.\n-> Next\n===\n"
        "title: Next\n---\nBob: Goodbye.\n===\n"
    )
    return path


def write_ink(path):
    open(path, "w", encoding="utf-8").write(
        "=== start ===\nAlice: Hello there.\n* Go on -> next\n\n=== next ===\nBob: Goodbye.\n-> END\n"
    )
    return path


def write_fnt(path, page_png="label.png"):
    open(path, "w", encoding="utf-8").write(
        'info face="tiny" size=8 bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=0 aa=1 padding=0,0,0,0 spacing=1,1\n'
        "common lineHeight=8 base=6 scaleW=16 scaleH=16 pages=1 packed=0\n"
        f'page id=0 file="{page_png}"\n'
        "chars count=3\n"
        "char id=65 x=0 y=0 width=6 height=8 xoffset=0 yoffset=0 xadvance=6 page=0 chnl=15\n"
        "char id=66 x=6 y=0 width=6 height=8 xoffset=0 yoffset=0 xadvance=6 page=0 chnl=15\n"
        "char id=32 x=12 y=0 width=3 height=8 xoffset=0 yoffset=0 xadvance=3 page=0 chnl=15\n"
    )
    return path



# 400 tile ids as a zstd frame (Huffman literals + sequences + content checksum), made by the reference zstd library
ZSTD_TILES_B64 = ("KLUv/WRABSUIAPJHCwvgGcYAICieraXcKeAAAJ+WouWj5/5xulJgxuDnpB+jRcv/d/11cCAOI2C+D2yoMd6lqbS/"
    "ATDIkCm6OxEgBAhGoBDRCAhpaaykMevwFWCcJH/FR+3OPLqvRvPSe/9bRhCPzGPTS/P+aXP4b3g5ye3+H2w9Tht6"
    "8WXev7y4DTJn4EN45zaGu+BS/hw74OL1fRBDxlH6lV35H12HG5e6qAezywukh8pSvf/4zPcJDtvOdNn0n+S7BNOx"
    "Q1iwbBqyj/zntd0aWv/CcOc9gbAOdoncwS+FL+fLfMKWzz7Vi2w51S/L4xzuZLw+4qRMH3pxUOWp97tNvXhfTxYg"
    "3LznZEANCDF0iQ==")


def write_tiled_zstd(path):
    rec = {"type": "map", "width": 20, "height": 20, "tilewidth": 8, "tileheight": 8, "orientation": "orthogonal",
           "infinite": False, "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4, "columns": 2, "image": "tiles.png",
                                            "imagewidth": 16, "imageheight": 16, "tilewidth": 8, "tileheight": 8}],
           "layers": [{"type": "tilelayer", "name": "ground", "width": 20, "height": 20, "encoding": "base64",
                       "compression": "zstd", "data": ZSTD_TILES_B64}]}
    json.dump(rec, open(path, "w"), indent=2)
    return path


def write_tmx_zstd(path):
    open(path, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<map version="1.10" orientation="orthogonal" width="20" height="20" '
        'tilewidth="8" tileheight="8" infinite="0">\n <layer id="1" name="ground" width="20" height="20">\n'
        '  <data encoding="base64" compression="zstd">%s</data>\n </layer>\n</map>\n' % ZSTD_TILES_B64)
    return path


def write_colliders(path, tw=8, th=8):
    json.dump({"tile": [tw, th], "rects": [{"x": 8, "y": 0, "w": 8, "h": 16, "tx": 1, "ty": 0, "tw": 1, "th": 2},
                                         {"x": 0, "y": 16, "w": 16, "h": 8, "tx": 0, "ty": 2, "tw": 2, "th": 1}]},
              open(path, "w"), indent=1)
    return path


def write_fnt_xml(path, page_png="label.png"):
    open(path, "w", encoding="utf-8").write(
        '<?xml version="1.0"?>\n<font>\n <info face="tiny" size="8" unicode="1" padding="0,0,0,0" spacing="1,1"/>\n'
        ' <common lineHeight="8" base="6" scaleW="16" scaleH="16" pages="1" packed="0"/>\n'
        f' <pages><page id="0" file="{page_png}"/></pages>\n <chars count="2">\n'
        '  <char id="65" x="0" y="0" width="6" height="8" xoffset="0" yoffset="0" xadvance="6" page="0" chnl="15"/>\n'
        '  <char id="66" x="6" y="0" width="6" height="8" xoffset="0" yoffset="0" xadvance="6" page="0" chnl="15"/>\n'
        ' </chars>\n <kernings count="1"><kerning first="65" second="66" amount="-1"/></kernings>\n</font>\n')
    return path


def write_fnt_bin(path, page_png="label.png"):
    def block(kind, data):
        return struct.pack("<BI", kind, len(data)) + data
    info = struct.pack("<hBBHBBBBBBBB", 8, 0, 0, 100, 1, 0, 0, 0, 0, 1, 1, 0) + b"tiny\x00"
    common = struct.pack("<HHHHHBBBBB", 8, 6, 16, 16, 1, 0, 0, 0, 0, 0)
    chars = b"".join(struct.pack("<IHHHHhhhBB", i, x, 0, 6, 8, 0, 0, 6, 0, 15) for i, x in ((65, 0), (66, 6)))
    open(path, "wb").write(b"BMF\x03" + block(1, info) + block(2, common) + block(3, page_png.encode() + b"\x00")
                           + block(4, chars) + block(5, struct.pack("<IIh", 65, 66, -1)))
    return path


def write_ase(path, w=2, h=2, duration=100):
    """Minimal 32-bit one-frame Aseprite file (raw RGBA cel, one visible layer)."""
    def pstr(s):
        b = s.encode("utf-8")
        return struct.pack("<H", len(b)) + b
    rgba = (b"\xff\x00\x00\xff" * (w * h))
    layer_payload = struct.pack("<HHHHHHB", 1, 0, 0, 0, 0, 0, 255) + b"\x00\x00\x00" + pstr("Layer 1")
    layer_chunk = struct.pack("<IH", 6 + len(layer_payload), 0x2004) + layer_payload
    cel_payload = struct.pack("<HhhBH", 0, 0, 0, 255, 0) + b"\x00" * 7 + struct.pack("<HH", w, h) + rgba
    cel_chunk = struct.pack("<IH", 6 + len(cel_payload), 0x2005) + cel_payload
    tag_body = struct.pack("<H", 2) + b"\x00" * 8
    for name, direction, repeat in (("idle", 2, 0), ("hit", 1, 2)):
        tag_body += struct.pack("<HHBH", 0, 0, direction, repeat) + b"\x00" * 6 + b"\xff\x00\x00\x00" + pstr(name)
    tag_chunk = struct.pack("<IH", 6 + len(tag_body), 0x2018) + tag_body
    chunks = layer_chunk + cel_chunk + tag_chunk
    nchunks = 3
    frame = struct.pack("<IHHH2sI", 16 + len(chunks), 0xF1FA, nchunks, duration, b"\x00\x00", 0) + chunks
    header = bytearray(128)
    struct.pack_into("<IHHHHHIH", header, 0, 128 + len(frame), 0xA5E0, 1, w, h, 32, 1, duration)
    struct.pack_into("<H", header, 32, 256)
    open(path, "wb").write(bytes(header) + frame)
    return path


def write_tsx_atlas(path):
    """External image-atlas tileset with an animated tile (2.2.0)."""
    open(path, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<tileset version="1.10" name="atlas" tilewidth="8" tileheight="8" tilecount="4" columns="2" objectalignment="topleft">\n'
        ' <tileoffset x="1" y="-1"/>\n <image source="tiles.png" width="16" height="16"/>\n'
        ' <tile id="0"><animation><frame tileid="0" duration="100"/><frame tileid="1" duration="200"/></animation></tile>\n'
        '</tileset>\n')
    return path


def write_tsx_collection(path):
    """External image-collection tileset (one image per tile)."""
    open(path, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<tileset version="1.10" name="coll" tilewidth="8" tileheight="8" tilecount="2" columns="0">\n'
        ' <tile id="0"><image source="label.png" width="16" height="16"/></tile>\n'
        ' <tile id="1"><image source="tiles.png" width="16" height="16"/></tile>\n</tileset>\n')
    return path


def write_tiled_anim(path):
    rec = {"type": "map", "width": 4, "height": 3, "tilewidth": 8, "tileheight": 8, "orientation": "orthogonal",
           "infinite": False,
           "tilesets": [{"name": "t", "firstgid": 1, "tilecount": 4, "columns": 2, "image": "tiles.png", "imagewidth": 16,
                         "imageheight": 16, "tilewidth": 8, "tileheight": 8,
                         "tiles": [{"id": 0, "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 300}]}]},
                        {"name": "c", "firstgid": 10, "tilecount": 1, "columns": 0, "tilewidth": 8, "tileheight": 8,
                         "tiles": [{"id": 0, "image": "label.png", "imagewidth": 16, "imageheight": 16}]}],
           "layers": [{"type": "objectgroup", "name": "things", "objects": [
               {"id": 1, "gid": 1, "x": 0, "y": 8, "width": 8, "height": 8},
               {"id": 2, "gid": 1 | 0x20000000 | 0x80000000, "x": 8, "y": 16, "width": 8, "height": 8},
               {"id": 3, "gid": 10, "x": 16, "y": 8}]}]}
    json.dump(rec, open(path, "w"), indent=2)
    return path


def write_tmx_ext(path):
    """TMX that uses two external .tsx files (seed_atlas.tsx and seed_coll.tsx beside it)."""
    open(path, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<map version="1.10" orientation="orthogonal" width="4" height="3" '
        'tilewidth="8" tileheight="8" infinite="0">\n <tileset firstgid="1" source="seed_atlas.tsx"/>\n'
        ' <tileset firstgid="10" source="seed_coll.tsx"/>\n'
        ' <layer id="1" name="ground" width="4" height="3"><data encoding="csv">\n1,2,3,4,\n0,0,0,0,\n10,11,0,0\n</data></layer>\n'
        ' <objectgroup id="2" name="things">\n  <object id="1" gid="1" x="0" y="8" width="8" height="8"/>\n'
        '  <object id="2" gid="10" x="16" y="8"/>\n </objectgroup>\n</map>\n')
    return path


def write_ase_json(path):
    frames = [{"filename": "f%d" % i, "frame": {"x": i * 4, "y": 0, "w": 4, "h": 4}, "rotated": False, "trimmed": False,
               "spriteSourceSize": {"x": 0, "y": 0, "w": 4, "h": 4}, "sourceSize": {"w": 4, "h": 4}, "duration": 100 + i}
              for i in range(4)]
    tags = [{"name": "idle", "from": 0, "to": 1, "direction": "forward"},
            {"name": "run", "from": 0, "to": 3, "direction": "pingpong"},
            {"name": "back", "from": 1, "to": 3, "direction": "reverse", "repeat": "2"},
            {"name": "ppr", "from": 0, "to": 2, "direction": "pingpong_reverse"}]
    json.dump({"frames": frames, "meta": {"app": "http://www.aseprite.org/", "image": "seed.png", "size": {"w": 16, "h": 4},
                                          "frameTags": tags, "slices": []}}, open(path, "w"), indent=1)
    return path


def write_colliders_partial(path, tw=8, th=8):
    json.dump({"tile": [tw, th], "rects": [{"x": 4, "y": 2.5, "w": 7, "h": 9}, {"x": 12, "y": 0, "w": 3.5, "h": 40}]},
              open(path, "w"), indent=1)
    return path


def generate(dest):
    """Write one seed of each kind into dest. Returns {kind: [paths]}."""
    os.makedirs(dest, exist_ok=True)
    out = {k: [] for k in KINDS}
    out["wav"].append(write_wav(os.path.join(dest, "seed.wav")))
    out["png"].append(write_png(os.path.join(dest, "seed.png")))
    # tileset image used by tiled/tmx seeds
    write_png(os.path.join(dest, "tiles.png"), 16, 16)
    out["gif"].append(write_gif(os.path.join(dest, "seed.gif"), 1, 1))
    out["tiled"].append(write_tiled(os.path.join(dest, "seed.json")))
    out["tmx"].append(write_tmx(os.path.join(dest, "seed.tmx")))
    out["obj"].append(write_obj(os.path.join(dest, "seed.obj")))
    out["gltf"].append(write_gltf(os.path.join(dest, "seed.gltf")))
    out["glb"].append(write_glb(os.path.join(dest, "seed.glb")))
    jp, png = write_atlas(dest, "atlas")
    out["atlas"].append(jp)
    out["png"].append(png)  # atlas sheet is also a png seed
    out["loc"].append(write_loc(os.path.join(dest, "seed.csv")))
    out["yarn"].append(write_yarn(os.path.join(dest, "seed.yarn")))
    out["ink"].append(write_ink(os.path.join(dest, "seed.ink")))
    write_png(os.path.join(dest, "label.png"), 16, 16)
    out["fnt"].append(write_fnt(os.path.join(dest, "seed.fnt"), "label.png"))
    out["tiledzstd"].append(write_tiled_zstd(os.path.join(dest, "seed_zstd.json")))
    out["tmxzstd"].append(write_tmx_zstd(os.path.join(dest, "seed_zstd.tmx")))
    out["colliders"].append(write_colliders(os.path.join(dest, "seed_colliders.json")))
    out["fntxml"].append(write_fnt_xml(os.path.join(dest, "seed_xml.fnt"), "label.png"))
    out["fntbin"].append(write_fnt_bin(os.path.join(dest, "seed_bin.fnt"), "label.png"))
    out["ase"].append(write_ase(os.path.join(dest, "seed.ase")))
    out["tsx"].append(write_tsx_atlas(os.path.join(dest, "seed_atlas.tsx")))
    write_tsx_collection(os.path.join(dest, "seed_coll.tsx"))
    out["tiledanim"].append(write_tiled_anim(os.path.join(dest, "seed_anim.json")))
    out["tmxext"].append(write_tmx_ext(os.path.join(dest, "seed_ext.tmx")))
    out["asejson"].append(write_ase_json(os.path.join(dest, "seed_asejson.json")))
    out["colliders"].append(write_colliders_partial(os.path.join(dest, "seed_colliders_partial.json")))
    # second small wav / png for two-input tools
    out["wav"].append(write_wav(os.path.join(dest, "seed2.wav"), frames=32))
    out["png"].append(write_png(os.path.join(dest, "seed2.png"), 4, 4))
    out["tiled"].append(write_tiled(os.path.join(dest, "seed2.json"), w=3, h=3))
    out["obj"].append(write_obj(os.path.join(dest, "seed2.obj")))
    out["glb"].append(write_glb(os.path.join(dest, "seed2.glb")))
    out["loc"].append(write_loc(os.path.join(dest, "seed2.csv")))
    jp2, _ = write_atlas(dest, "atlas2")
    out["atlas"].append(jp2)
    return out
