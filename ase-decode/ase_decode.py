#!/usr/bin/env python3
"""ase-decode: read a binary Aseprite `.ase` / `.aseprite` file and export frames as PNG plus a JSON of tags and layers.

Implements the public Aseprite file format (header, frames, layers, cels,
tags, palette) so you do not need the Aseprite app. Raw and zlib-compressed
cels at 8-bit indexed (with palette) and 32-bit RGBA are composited in
layer order. Linked cels, 16-bit grayscale and tilemap cels are reported
but 16-bit / tilemap pixels are not decoded (known gap). The input is
never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, struct, sys, zlib

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402

MAGIC, FRAME_MAGIC = 0xA5E0, 0xF1FA
CHUNK_LAYER, CHUNK_CEL, CHUNK_TAGS, CHUNK_PAL = 0x2004, 0x2005, 0x2018, 0x2019


def _need(data, off, n, what):
    if off + n > len(data):
        raise GstInputError("Aseprite %s exceeds file" % what)
    return off


def read_string(data, off):
    _need(data, off, 2, "string length")
    n = struct.unpack_from("<H", data, off)[0]
    off += 2
    _need(data, off, n, "string")
    try:
        s = data[off:off + n].decode("utf-8")
    except UnicodeDecodeError as e:
        raise GstInputError("Aseprite string is not valid UTF-8") from e
    return s, off + n


def parse(data):
    if not isinstance(data, (bytes, bytearray)) or len(data) < 128:
        raise GstInputError("not an Aseprite file (truncated header)")
    size, magic, nframes, width, height, depth, flags, speed = struct.unpack_from("<IHHHHHIH", data, 0)
    if magic != MAGIC:
        raise GstInputError("not an Aseprite file (bad magic)")
    if width < 1 or height < 1:
        raise GstInputError("Aseprite canvas size is invalid")
    if depth not in (8, 16, 32):
        raise GstInputError("Aseprite unsupported color depth %s" % depth)
    transparent = data[28]
    ncolors = struct.unpack_from("<H", data, 32)[0] or 256
    header = {
        "width": width, "height": height, "depth": depth, "frames": nframes,
        "speed": speed, "flags": flags, "transparent": transparent, "colors": ncolors,
        "declared_size": size,
    }
    layers, tags, palette = [], [], None
    frames = []  # list of {duration, cels: [...]}
    off = 128
    for fi in range(nframes):
        _need(data, off, 16, "frame header")
        fsize, fmagic, old_chunks, duration, _res, new_chunks = struct.unpack_from("<IHHH2sI", data, off)
        if fmagic != FRAME_MAGIC:
            raise GstInputError("Aseprite frame magic is invalid")
        nchunks = new_chunks if old_chunks == 0xFFFF else (new_chunks or old_chunks)
        frame_end = off + fsize
        if frame_end > len(data):
            raise GstInputError("Aseprite frame length exceeds file")
        pos = off + 16
        cels = []
        for _ in range(nchunks):
            _need(data, pos, 6, "chunk header")
            csize, ctype = struct.unpack_from("<IH", data, pos)
            if csize < 6 or pos + csize > frame_end:
                raise GstInputError("Aseprite chunk length exceeds frame")
            payload, next_pos = data[pos + 6:pos + csize], pos + csize
            if ctype == CHUNK_LAYER:
                layers.append(_parse_layer(payload))
            elif ctype == CHUNK_CEL:
                cels.append(_parse_cel(payload, depth))
            elif ctype == CHUNK_TAGS:
                tags.extend(_parse_tags(payload))
            elif ctype == CHUNK_PAL:
                palette = _parse_palette(payload, palette)
            pos = next_pos
        frames.append({"duration": duration, "cels": cels})
        off = frame_end
    if palette is None:
        # grayscale fallback for 8-bit
        palette = [(i, i, i, 255) for i in range(256)]
        if 0 <= transparent < 256:
            r, g, b, _a = palette[transparent]
            palette[transparent] = (r, g, b, 0)
    return header, layers, frames, tags, palette


def _parse_layer(payload):
    if len(payload) < 16:
        raise GstInputError("Aseprite layer chunk is truncated")
    flags, typ, child, _w, _h, blend, opacity = struct.unpack_from("<HHHHHHB", payload, 0)
    name, _ = read_string(payload, 16)  # 6*H + opacity + 3 unused
    # layout: flags, type, child, defaultW, defaultH, blend (6*H=12) + opacity B + 3 unused = 16, then string
    return {"name": name, "flags": flags, "type": typ, "child_level": child, "blend": blend, "opacity": opacity,
            "visible": bool(flags & 1)}


def _parse_cel(payload, depth):
    if len(payload) < 16:
        raise GstInputError("Aseprite cel chunk is truncated")
    # WORD layer, SHORT x, SHORT y, BYTE opacity, WORD type, BYTE[7] unused
    layer, x, y, opacity, typ = struct.unpack_from("<HhhBH", payload, 0)
    rest = payload[16:]
    cel = {"layer": layer, "x": x, "y": y, "opacity": opacity, "type": typ, "pixels": None, "w": 0, "h": 0, "link": None}
    if typ == 1:
        if len(rest) < 2:
            raise GstInputError("Aseprite linked cel is truncated")
        cel["link"] = struct.unpack_from("<H", rest, 0)[0]
        return cel
    if typ in (0, 2):
        if len(rest) < 4:
            raise GstInputError("Aseprite cel pixels header is truncated")
        w, h = struct.unpack_from("<HH", rest, 0)
        raw = rest[4:]
        if typ == 2:
            try:
                raw = zlib.decompress(raw)
            except zlib.error as e:
                raise GstInputError("Aseprite cel zlib data is not valid") from e
        bpp = {8: 1, 16: 2, 32: 4}[depth]
        expect = w * h * bpp
        if len(raw) < expect:
            raise GstInputError("Aseprite cel pixel data is truncated")
        cel.update({"w": w, "h": h, "pixels": raw[:expect]})
        return cel
    # type 3 tilemap or unknown: leave pixels None
    return cel


DIRECTIONS = {0: "forward", 1: "reverse", 2: "pingpong", 3: "pingpong_reverse"}


def _parse_tags(payload):
    if len(payload) < 10:
        raise GstInputError("Aseprite tags chunk is truncated")
    n = struct.unpack_from("<H", payload, 0)[0]
    off = 2 + 8
    tags = []
    for _ in range(n):
        _need(payload, off, 17, "tag")
        # WORD from, WORD to, BYTE loop, WORD repeat, BYTE[6] reserved, BYTE[3] rgb, BYTE extra, STRING
        frm, to, loop, repeat = struct.unpack_from("<HHBH", payload, off)
        off += 2 + 2 + 1 + 2 + 6 + 3 + 1
        name, off = read_string(payload, off)
        # the byte the old output called "loop" is Aseprite's animation direction; keep the key for old callers
        tags.append({"name": name, "from": frm, "to": to, "loop": loop, "repeat": repeat,
                     "direction": DIRECTIONS.get(loop, "forward")})
    return tags


def _parse_palette(payload, prev):
    if len(payload) < 20:
        raise GstInputError("Aseprite palette chunk is truncated")
    size, first, last = struct.unpack_from("<III", payload, 0)
    off = 4 + 4 + 4 + 8
    pal = list(prev) if prev is not None else [(0, 0, 0, 0)] * max(256, size)
    while len(pal) < size:
        pal.append((0, 0, 0, 0))
    for i in range(first, last + 1):
        _need(payload, off, 6, "palette entry")
        flags, r, g, b, a = struct.unpack_from("<HBBBB", payload, off)
        off += 6
        if flags & 1:
            _name, off = read_string(payload, off)
        if 0 <= i < len(pal):
            pal[i] = (r, g, b, a)
        elif i == len(pal):
            pal.append((r, g, b, a))
    return pal


def cel_image(cel, depth, palette):
    if cel.get("pixels") is None or cel["w"] < 1 or cel["h"] < 1:
        return None
    w, h, raw = cel["w"], cel["h"], cel["pixels"]
    if depth == 32:
        return Image.frombytes("RGBA", (w, h), raw)
    if depth == 8:
        im = Image.frombytes("P", (w, h), raw)
        flat = []
        for r, g, b, a in palette[:256]:
            flat.extend((r, g, b))
        while len(flat) < 768:
            flat.extend((0, 0, 0))
        im.putpalette(flat)
        # apply alpha from palette via RGBA convert with a mask
        rgba = im.convert("RGBA")
        px = rgba.load()
        src = raw
        for y in range(h):
            for x in range(w):
                idx = src[y * w + x]
                if idx < len(palette):
                    r, g, b, a = palette[idx]
                    px[x, y] = (r, g, b, a)
        return rgba
    return None  # 16-bit not decoded


def composite(header, layers, frames, palette):
    w, h, depth = header["width"], header["height"], header["depth"]
    # resolve links after all frames exist
    images = []
    cel_imgs = []  # per frame, list of (layer, x, y, opacity, Image or None)
    for fr in frames:
        recs = []
        for cel in fr["cels"]:
            recs.append(cel)
        cel_imgs.append(recs)
    out = []
    for fi, fr in enumerate(frames):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        # layer order: document order, skip invisible / group
        by_layer = {c["layer"]: c for c in fr["cels"]}
        # multiple cels per layer possible? last wins for this simple impl; actually one cel per layer per frame typically
        for li, layer in enumerate(layers):
            if layer.get("type") == 1:
                continue
            if not layer.get("visible", True):
                continue
            cel = by_layer.get(li)
            if cel is None:
                continue
            src_cel = cel
            if cel["type"] == 1 and cel.get("link") is not None:
                link = cel["link"]
                if 0 <= link < len(frames):
                    for c2 in frames[link]["cels"]:
                        if c2["layer"] == li and c2["type"] != 1:
                            src_cel = c2
                            break
            im = cel_image(src_cel, depth, palette)
            if im is None:
                continue
            op = (cel["opacity"] / 255.0) * (layer.get("opacity", 255) / 255.0)
            if op <= 0:
                continue
            if op < 1:
                r, g, b, a = im.split()
                a = a.point(lambda v, o=op: int(v * o))
                im = Image.merge("RGBA", (r, g, b, a))
            canvas.alpha_composite(im, (src_cel["x"], src_cel["y"]))
        out.append(canvas)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export frames and tags from a binary Aseprite file.")
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--prefix", default="frame")
    ap.add_argument("--json")
    ap.add_argument("--no-png", action="store_true", help="write JSON only")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.outdir, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    try:
        data = open(a.input, "rb").read()
    except OSError as e:
        raise GstInputError("cannot read file: %s" % e) from e
    header, layers, frames, tags, palette = parse(data)
    images = composite(header, layers, frames, palette)
    os.makedirs(a.outdir, exist_ok=True)
    names = []
    if not a.no_png:
        for i, im in enumerate(images):
            name = "%s_%04d.png" % (a.prefix, i)
            im.save(os.path.join(a.outdir, name))
            names.append({"file": name, "duration_ms": frames[i]["duration"]})
    rec = {
        "width": header["width"], "height": header["height"], "depth": header["depth"],
        "frames": names if names else [{"duration_ms": fr["duration"]} for fr in frames],
        "layers": [{"name": l["name"], "visible": l["visible"], "opacity": l["opacity"]} for l in layers],
        "tags": tags,
        "undecoded": [],
    }
    if header["depth"] == 16:
        rec["undecoded"].append("16-bit grayscale cels are not composited")
    if any(c["type"] == 3 for fr in frames for c in fr["cels"]):
        rec["undecoded"].append("tilemap cels are not composited")
    meta_path = a.json or os.path.join(a.outdir, "ase.json")
    json.dump(rec, open(meta_path, "w"), indent=2)
    rec["json"] = meta_path
    print("%d frame(s), %d layer(s), %d tag(s) -> %s" % (len(frames), len(layers), len(tags), a.outdir))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
