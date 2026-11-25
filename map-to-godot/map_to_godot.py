#!/usr/bin/env python3
"""map-to-godot: write a Godot 4.x TileMapLayer scene (`.tscn`) from a Tiled JSON or TMX map.

Each Tiled tile layer becomes a TileMapLayer whose `tile_map_data` is the
Godot 4.7 packed-byte format (uint16 format=0, then per cell: int16 x, y,
uint16 source_id, int16 atlas_x, atlas_y, uint16 alternative_tile), verified
against official Godot 4.7.2. TileSet sources follow the map's tilesets in
order (source_id 0, 1, ...). Optional `--write-tileset` also writes a
`.tres`. Tiled H/V/diagonal flip flags become TileSetAtlasSource alternative
tiles (`flip_h` / `flip_v` / `transpose`) and the cell's `alternative_tile`
index. Object layers are listed in `--json` but not turned into nodes (see
map-objects-to-godot). The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmx-to-json"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import map_diff  # noqa: E402

FLIP_H, FLIP_V, FLIP_D = 0x80000000, 0x40000000, 0x20000000
GID_MASK = 0x1FFFFFFF


def flags_to_alt(flags: int) -> int:
    """Stable alternative id: bit 0 = H, bit 1 = V, bit 2 = diagonal (transpose)."""
    alt = 0
    if flags & FLIP_H:
        alt |= 1
    if flags & FLIP_V:
        alt |= 2
    if flags & FLIP_D:
        alt |= 4
    return alt


def alt_props(alt: int) -> dict:
    return {"flip_h": bool(alt & 1), "flip_v": bool(alt & 2), "transpose": bool(alt & 4)}


def encode_tile_map_data(cells, fmt=0):
    """cells: iterable of (x, y, source_id, atlas_x, atlas_y, alt). Returns bytes."""
    buf = [struct.pack("<H", int(fmt))]
    for x, y, sid, ax, ay, alt in cells:
        buf.append(struct.pack("<hhHhhH", int(x), int(y), int(sid), int(ax), int(ay), int(alt)))
    return b"".join(buf)


def packed_byte_array_literal(data: bytes) -> str:
    return "PackedByteArray(" + ", ".join(str(b) for b in data) + ")"


def load_map(path):
    low = path.lower()
    if low.endswith((".tmx", ".xml")):
        import tmx_to_json
        try:
            doc = tmx_to_json.convert(path)
        except SystemExit as e:
            raise GstInputError(str(e.code) if e.code not in (None, 1) and not isinstance(e.code, int) else (e.code if isinstance(e.code, str) else "not a TMX map"))
        except Exception as e:
            if type(e).__name__ in ("ParseError", "GstInputError"):
                raise GstInputError("TMX is not well-formed: %s" % e) from e
            raise
    else:
        doc = gst_read.require_object(gst_read.load_json(path, "Tiled map"), "Tiled map")
    base = os.path.dirname(os.path.abspath(path))
    try:
        doc = map_diff.decode_map(doc)
        doc = map_diff.resolve_map_tilesets(doc, base)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError) as e:
        raise GstInputError("map has an unusable value (%s: %s)" % (type(e).__name__, e)) from e
    return doc


def gid_to_cell(gid, tilesets):
    """Return (source_id, atlas_x, atlas_y, flags) or None if empty / unknown."""
    flags = gid & (FLIP_H | FLIP_V | FLIP_D)
    raw = gid & GID_MASK
    if raw == 0:
        return None
    match = None
    for i, ts in enumerate(tilesets):
        fg = int(ts.get("firstgid") or 1)
        if raw >= fg:
            match = (i, ts, fg)
    if match is None:
        return None
    sid, ts, fg = match
    local = raw - fg
    cols = int(ts.get("columns") or 0)
    if cols <= 0:
        tw = int(ts.get("tilewidth") or 0)
        iw = int(ts.get("imagewidth") or 0)
        if tw > 0 and iw > 0:
            cols = max(1, iw // tw)
    if cols <= 0:
        cols = 1
    ax, ay = local % cols, local // cols
    return sid, ax, ay, int(flags)


def collect_layers(doc):
    tilesets = doc.get("tilesets") or []
    layers_out, flipped, unknown, cells_total = [], 0, 0, 0
    objects = []

    def walk(layers, prefix=""):
        nonlocal flipped, unknown, cells_total
        for l in layers or []:
            typ = l.get("type")
            name = prefix + (l.get("name") or "layer")
            if typ == "group":
                walk(l.get("layers") or [], name + "/")
                continue
            if typ == "objectgroup":
                objects.append({"name": name, "objects": len(l.get("objects") or [])})
                continue
            if typ != "tilelayer":
                continue
            cells = []
            used = {}  # sid -> {(ax, ay): set of alt ids}
            for (x, y), gid in map_diff.cells(l).items():
                rec = gid_to_cell(gid, tilesets)
                if rec is None:
                    unknown += 1
                    continue
                sid, ax, ay, flags = rec
                alt = flags_to_alt(flags)
                if alt:
                    flipped += 1
                cells.append((int(x), int(y), sid, ax, ay, alt))
                used.setdefault(sid, {}).setdefault((ax, ay), set()).add(alt)
                cells_total += 1
            layers_out.append({"name": name, "cells": cells, "used": used, "visible": l.get("visible", True)})

    walk(doc.get("layers") or [])
    return layers_out, objects, {"cells": cells_total, "flipped_cells": flipped, "unknown_gids": unknown}


def merge_used(layers):
    used = {}
    for layer in layers:
        for sid, tiles in layer["used"].items():
            slot = used.setdefault(sid, {})
            for coord, alts in tiles.items():
                slot.setdefault(coord, set()).update(alts)
    return used


def write_tileset_tres(path, tilesets, used_by_source, res_prefix):
    """Write a TileSet .tres with one atlas source per Tiled tileset, plus flip alternatives."""
    ext, sources = [], []
    for i, ts in enumerate(tilesets):
        image = ts.get("image") or ""
        basename = os.path.basename(image) if image else ("tileset_%d.png" % i)
        if res_prefix.endswith("/") or res_prefix == "res://":
            res = res_prefix.rstrip("/") + "/" + basename
        elif res_prefix.startswith("res://") and i == 0 and len(tilesets) == 1:
            res = res_prefix
        elif res_prefix.startswith("res://"):
            res = res_prefix.rstrip("/") + "/" + basename
        else:
            res = "res://" + basename
        if not res.startswith("res://"):
            res = "res://" + basename
        eid = "%d_tex" % (i + 1)
        ext.append((res, eid, int(ts.get("tilewidth") or 16), int(ts.get("tileheight") or 16), used_by_source.get(i, {}), ts))
    load_steps = 1 + len(ext) + len(ext)
    lines = ['[gd_resource type="TileSet" load_steps=%d format=3]' % load_steps, ""]
    for res, eid, tw, th, used, ts in ext:
        lines.append('[ext_resource type="Texture2D" path="%s" id="%s"]' % (res, eid))
    lines.append("")
    tw0, th0 = (ext[0][2], ext[0][3]) if ext else (16, 16)
    for i, (res, eid, tw, th, used, ts) in enumerate(ext):
        sid = "TileSetAtlasSource_%d" % i
        lines.append('[sub_resource type="TileSetAtlasSource" id="%s"]' % sid)
        lines.append('texture = ExtResource("%s")' % eid)
        lines.append("texture_region_size = Vector2i(%d, %d)" % (tw, th))
        coords = sorted(used) if used else [(0, 0)]
        for ax, ay in coords:
            alts = set(used.get((ax, ay), {0})) if used else {0}
            alts.add(0)
            max_alt = max(alts)
            if max_alt > 0:
                lines.append("%d:%d/next_alternative_id = %d" % (ax, ay, max_alt + 1))
            lines.append("%d:%d/0 = 0" % (ax, ay))
            for alt in sorted(alts):
                if alt == 0:
                    continue
                lines.append("%d:%d/%d = %d" % (ax, ay, alt, alt))
                props = alt_props(alt)
                if props["flip_h"]:
                    lines.append("%d:%d/%d/flip_h = true" % (ax, ay, alt))
                if props["flip_v"]:
                    lines.append("%d:%d/%d/flip_v = true" % (ax, ay, alt))
                if props["transpose"]:
                    lines.append("%d:%d/%d/transpose = true" % (ax, ay, alt))
        lines.append("")
        sources.append(sid)
    lines.append("[resource]")
    lines.append("tile_size = Vector2i(%d, %d)" % (tw0, th0))
    for i, sid in enumerate(sources):
        lines.append('sources/%d = SubResource("%s")' % (i, sid))
    lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def write_tscn(path, layers, tileset_res):
    load_steps = 2
    lines = ['[gd_scene load_steps=%d format=3]' % load_steps, ""]
    lines.append('[ext_resource type="TileSet" path="%s" id="1_ts"]' % tileset_res)
    lines.append("")
    lines.append('[node name="Map" type="Node2D"]')
    lines.append("")
    used_names = {}
    for layer in layers:
        raw = layer["name"].replace("/", "_") or "Layer"
        name = raw
        n = used_names.get(name, 0)
        used_names[name] = n + 1
        if n:
            name = "%s_%d" % (raw, n)
        data = encode_tile_map_data(layer["cells"])
        lines.append('[node name="%s" type="TileMapLayer" parent="."]' % name)
        lines.append("tile_map_data = %s" % packed_byte_array_literal(data))
        lines.append('tile_set = ExtResource("1_ts")')
        if layer.get("visible") is False:
            lines.append("visible = false")
        lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 TileMapLayer .tscn from a Tiled map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True, help="output .tscn")
    ap.add_argument("--tileset", help="res:// path of the TileSet to reference (default: res://<mapstem>_tileset.tres)")
    ap.add_argument("--write-tileset", metavar="PATH", help="also write a TileSet .tres next to the scene (or at PATH)")
    ap.add_argument("--res", default="res://", help="res:// prefix for tileset textures (default res://)")
    ap.add_argument("--cells-json", help="also write a cells.json (layer name, x, y, source, atlas, alt, flips)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    for extra in (a.write_tileset, a.cells_json, a.json):
        if extra:
            safe_out.check(a.map, extra, a.in_place)
    doc = load_map(a.map)
    tw, th = int(doc.get("tilewidth") or 16), int(doc.get("tileheight") or 16)
    layers, objects, rec = collect_layers(doc)
    if not layers:
        raise GstInputError("Tiled map has no tile layers")
    stem = os.path.splitext(os.path.basename(a.map))[0]
    tileset_res = a.tileset or ("res://" + stem + "_tileset.tres")
    if a.write_tileset:
        ts_path = a.write_tileset
        write_tileset_tres(ts_path, doc.get("tilesets") or [], merge_used(layers), a.res)
        rec["tileset"] = ts_path
        if a.tileset is None:
            tileset_res = "res://" + os.path.basename(ts_path)
    write_tscn(a.out, layers, tileset_res)
    rec.update({
        "out": a.out,
        "tileset_res": tileset_res,
        "layers": [{"name": l["name"], "cells": len(l["cells"])} for l in layers],
        "objects": objects,
        "tilewidth": tw, "tileheight": th,
        "width": doc.get("width"), "height": doc.get("height"),
    })
    if a.cells_json:
        cells = []
        for l in layers:
            for x, y, sid, ax, ay, alt in l["cells"]:
                props = alt_props(alt)
                cells.append({
                    "layer": l["name"], "x": x, "y": y, "source": sid,
                    "atlas_x": ax, "atlas_y": ay, "alt": alt,
                    "flip_h": props["flip_h"], "flip_v": props["flip_v"],
                    "transpose": props["transpose"],
                })
        json.dump({"tilewidth": tw, "tileheight": th, "cells": cells}, open(a.cells_json, "w"), indent=1)
        rec["cells_json"] = a.cells_json
    extra = ""
    if rec["flipped_cells"]:
        extra = " (%d flipped GID(s) mapped to alternative tiles)" % rec["flipped_cells"]
    print("%d layer(s), %d cell(s) -> %s" % (len(layers), rec["cells"], a.out) + extra)
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
