#!/usr/bin/env python3
"""font-to-godot: write a Godot 4 Theme `.tres` that uses a BMFont `.fnt` as its default font.

Parses an AngelCode BMFont file (text, XML, or binary version 3), checks the
page image is present, and writes a Theme whose `default_font` ExtResource's
the `.fnt` (Godot's `font_data_bmfont` importer loads it as a FontFile).
Optional `--copy-dir` copies the `.fnt` and its page PNG next to the Theme or
into DIR. The input is never overwritten unless
`--in-place`.
"""
from __future__ import annotations

import argparse, json, os, re, shutil, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402
from PIL import Image  # noqa: E402


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary(fmt, pages, size, line_height, chars, glyphs=None, page_ids=None, scale=None):
    """`glyphs` is [(id, x, y, w, h, page)], `page_ids` maps a page id to its file, `scale` is (scaleW, scaleH)."""
    pages = [p for p in pages if p]
    if not pages:
        raise GstInputError("BMFont has no page file")
    if chars == 0:
        raise GstInputError("BMFont has no characters")
    return {"page": pages[0], "pages": pages, "size": abs(size) or 16, "line_height": line_height,
            "chars": chars, "format": fmt, "glyphs": glyphs or [],
            "page_ids": page_ids if page_ids is not None else {i: p for i, p in enumerate(pages)},
            "scale": scale}


def check_glyph_rects(info, sizes):
    """Raise GstInputError when a glyph rectangle is negative or lies outside its page image.

    `sizes` maps a page file name to the (width, height) of its image. A rectangle may touch the
    page edge (x + width == page width) but not pass it; zero-size glyphs (a space) are fine
    anywhere inside the page. A glyph that names a page the file does not declare is an error too.
    """
    bad, first = 0, None
    for gid, x, y, w, h, page in info["glyphs"]:
        name = info["page_ids"].get(page)
        problem = None
        if name is None:
            problem = "names page %d, which the font does not declare" % page
        elif w < 0 or h < 0 or x < 0 or y < 0:
            problem = "has a negative rectangle (x=%d y=%d width=%d height=%d)" % (x, y, w, h)
        else:
            pw, ph = sizes.get(name, (None, None))
            if pw is not None and (x + w > pw or y + h > ph):
                problem = "rectangle x=%d y=%d width=%d height=%d lies outside the %dx%d page %s" % (x, y, w, h, pw, ph, name)
        if problem:
            bad += 1
            first = first or "glyph id %d %s" % (gid, problem)
    if bad:
        raise GstInputError("BMFont glyph check failed: %s%s" % (first, "" if bad == 1 else " (and %d more glyph(s))" % (bad - 1)))


def _kv(line):
    """key=value pairs of a text BMFont line; values may be quoted."""
    return {k: (q or v) for k, q, v in re.findall(r'(\w+)=(?:"([^"]*)"|(\S*))', line)}


def _need_ints(kv, keys, what):
    out = []
    for k in keys:
        try:
            out.append(int(kv[k]))
        except (KeyError, ValueError):
            raise GstInputError("BMFont %s line has no valid %s" % (what, k)) from None
    return out


def parse_text(text):
    if not text.lstrip().startswith("info "):
        raise GstInputError("not a BMFont .fnt file")
    pages, page_ids, glyphs = [], {}, []
    size, line_height, chars, scale = 16, 16, 0, None
    for line in text.splitlines():
        if line.startswith("info "):
            m = re.search(r"\bsize=(-?\d+)", line)
            if m:
                size = int(m.group(1))
        elif line.startswith("common "):
            m = re.search(r"\blineHeight=(-?\d+)", line)
            if m:
                line_height = int(m.group(1))
            kv = _kv(line)
            if "scaleW" in kv and "scaleH" in kv:
                scale = tuple(_need_ints(kv, ("scaleW", "scaleH"), "common"))
        elif line.startswith("page "):
            m = re.search(r'file="([^"]+)"', line) or re.search(r"file=(\S+)", line)
            if m:
                pages.append(m.group(1).strip().strip('"'))
                page_ids[_int(_kv(line).get("id"), len(page_ids))] = pages[-1]
        elif line.startswith("char "):
            chars += 1
            kv = _kv(line)
            gid, x, y, w, h = _need_ints(kv, ("id", "x", "y", "width", "height"), "char")
            glyphs.append((gid, x, y, w, h, _int(kv.get("page"), 0)))
    return _summary("text", pages, size, line_height, chars, glyphs, page_ids, scale)


def parse_xml(raw):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise GstInputError("BMFont XML does not parse: %s" % e)
    if root.tag != "font":
        raise GstInputError("not a BMFont XML file (root element is <%s>)" % root.tag)
    info, common = root.find("info"), root.find("common")
    pages, page_ids = [], {}
    for p in root.findall("./pages/page"):
        if p.get("file"):
            pages.append(p.get("file"))
            page_ids[_int(p.get("id"), len(page_ids))] = p.get("file")
    glyphs = []
    for el in root.findall("./chars/char"):
        gid, x, y, w, h = _need_ints(el.attrib, ("id", "x", "y", "width", "height"), "char")
        glyphs.append((gid, x, y, w, h, _int(el.get("page"), 0)))
    scale = None
    if common is not None and common.get("scaleW") and common.get("scaleH"):
        scale = tuple(_need_ints(common.attrib, ("scaleW", "scaleH"), "common"))
    return _summary("xml", pages,
                    _int(info.get("size"), 16) if info is not None else 16,
                    _int(common.get("lineHeight"), 16) if common is not None else 16, len(glyphs),
                    glyphs, page_ids, scale)


def parse_binary(raw):
    """AngelCode binary BMFont version 3: 'BMF' 3 then (type, size, data) blocks."""
    if len(raw) < 4 or raw[3] != 3:
        raise GstInputError("binary BMFont version %s is not supported (only version 3)" % (raw[3] if len(raw) > 3 else "?"))
    off = 4
    size, line_height, chars, pages = 16, 16, 0, []
    glyphs, scale = [], None
    seen = set()
    while off < len(raw):
        if off + 5 > len(raw):
            raise GstInputError("binary BMFont is truncated (block header)")
        kind = raw[off]
        length = struct.unpack_from("<I", raw, off + 1)[0]
        off += 5
        if length > len(raw) - off:
            raise GstInputError("binary BMFont block %d is longer than the file" % kind)
        block = raw[off:off + length]
        off += length
        if kind in seen and kind != 5:
            raise GstInputError("binary BMFont has a duplicate block %d" % kind)
        seen.add(kind)
        if kind == 1:
            if len(block) < 15:
                raise GstInputError("binary BMFont info block is too short")
            size = struct.unpack_from("<h", block, 0)[0]
        elif kind == 2:
            if len(block) < 15:
                raise GstInputError("binary BMFont common block is too short")
            line_height = struct.unpack_from("<H", block, 0)[0]
            scale = struct.unpack_from("<HH", block, 4)
        elif kind == 3:
            pages = [n.decode("utf-8", "replace") for n in block.split(b"\x00") if n]
        elif kind == 4:
            if len(block) % 20:
                raise GstInputError("binary BMFont chars block is not a whole number of 20-byte records")
            chars = len(block) // 20
            glyphs = [(r[0], r[1], r[2], r[3], r[4], r[8]) for r in struct.iter_unpack("<IHHHHhhhBB", block)]
        elif kind == 5 and len(block) % 10:
            raise GstInputError("binary BMFont kerning block is not a whole number of 10-byte records")
    for need, label in ((1, "info"), (2, "common"), (3, "pages"), (4, "chars")):
        if need not in seen:
            raise GstInputError("binary BMFont has no %s block" % label)
    return _summary("binary", pages, size, line_height, chars, glyphs, None, scale)


def parse_fnt(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"BMF"):
        return parse_binary(raw)
    if raw.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        return parse_xml(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "replace")
    return parse_text(text)


_TEXT_QUOTED = ("face", "charset", "file")


def _attrs(el):
    parts = []
    for k, v in el.attrib.items():
        v = str(v)
        if k in _TEXT_QUOTED or " " in v or not v:
            v = '"%s"' % v.replace('"', "'")
        parts.append("%s=%s" % (k, v))
    return " ".join(parts)


def xml_to_text(raw):
    """Convert an XML BMFont document to the text BMFont format (every attribute is kept)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise GstInputError("BMFont XML does not parse: %s" % e)
    lines = []
    for name in ("info", "common"):
        el = root.find(name)
        if el is not None:
            lines.append("%s %s" % (name, _attrs(el)))
    for el in root.findall("./pages/page"):
        lines.append("page %s" % _attrs(el))
    chars = root.findall("./chars/char")
    lines.append("chars count=%d" % len(chars))
    lines.extend("char %s" % _attrs(el) for el in chars)
    kern = root.findall("./kernings/kerning")
    if kern:
        lines.append("kernings count=%d" % len(kern))
        lines.extend("kerning %s" % _attrs(el) for el in kern)
    return "\n".join(lines) + "\n"


def write_theme(path, font_res, font_size):
    lines = [
        '[gd_resource type="Theme" format=3]',
        "",
        '[ext_resource type="FontFile" path="%s" id="1_font"]' % font_res,
        "",
        "[resource]",
        'default_font = ExtResource("1_font")',
        "default_font_size = %d" % int(font_size),
        "",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 Theme .tres from a BMFont .fnt.")
    ap.add_argument("fnt")
    ap.add_argument("-o", "--out", required=True, help="output Theme .tres")
    ap.add_argument("--res", default="res://", help="res:// path or prefix for the .fnt")
    ap.add_argument("--copy-dir", metavar="DIR", help="copy the .fnt and page image into DIR")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.fnt, a.out, a.in_place)
    if a.json:
        safe_out.check(a.fnt, a.json, a.in_place)
    info = parse_fnt(a.fnt)
    here = os.path.dirname(os.path.abspath(a.fnt))
    page_paths = [os.path.join(here, p) for p in info["pages"]]
    for page_path in page_paths:
        if not os.path.isfile(page_path):
            raise GstInputError("BMFont page image is missing: %s" % page_path)
    sizes = {}
    for name, page_path in zip(info["pages"], page_paths):
        try:
            with Image.open(page_path) as im:
                sizes[name] = im.size
        except Exception as e:                      # a corrupt or non-image page is a typed input error
            raise GstInputError("BMFont page image %s is not a readable image: %s" % (page_path, e)) from e
    check_glyph_rects(info, sizes)
    scale_note = None
    if info["scale"] and info["pages"] and sizes.get(info["pages"][0]) not in (None, tuple(info["scale"])):
        scale_note = "common scaleW/scaleH %dx%d differs from the page image %dx%d" % (
            info["scale"][0], info["scale"][1], sizes[info["pages"][0]][0], sizes[info["pages"][0]][1])
    copied = []
    font_file = a.fnt
    font_name = os.path.basename(a.fnt)
    dest_dir = None
    if a.copy_dir:
        dest_dir = a.copy_dir if a.copy_dir != "." else (os.path.dirname(os.path.abspath(a.out)) or ".")
    converted = None
    if info["format"] == "xml":
        # Godot 4.7's importer reads text and binary BMFont but not XML, so write a text copy for it to import.
        font_name = os.path.splitext(font_name)[0] + "_text.fnt"
        converted = os.path.join(dest_dir or os.path.dirname(os.path.abspath(a.out)) or ".", font_name)
        safe_out.check(a.fnt, converted, a.in_place)
        os.makedirs(os.path.dirname(converted) or ".", exist_ok=True)
        open(converted, "w", encoding="utf-8").write(xml_to_text(open(a.fnt, "rb").read()))
        copied.append(converted)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
        for src in ([] if converted else [a.fnt]) + page_paths:
            dest = os.path.join(dest_dir, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dest):     # already in place: nothing to copy
                safe_out.check(a.fnt, dest, a.in_place)
                shutil.copy2(src, dest)
            copied.append(dest)
        font_res = godot_text.res_path(a.res, font_name)
    elif a.res.startswith("res://") and a.res.lower().endswith(".fnt"):
        font_res = a.res
    else:
        font_res = godot_text.res_path(a.res, font_name)
    write_theme(a.out, font_res, info["size"])
    rec = {"out": a.out, "font": font_res, "page": info["page"], "pages": info["pages"], "chars": info["chars"],
           "size": info["size"], "format": info["format"], "copied": copied,
           "page_sizes": {k: list(v) for k, v in sizes.items()}, "scale_note": scale_note}
    print("Theme %d char(s), size %d -> %s%s" % (info["chars"], info["size"], a.out, ("  [note: %s]" % scale_note) if scale_note else ""))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
