#!/usr/bin/env python3
"""godot-tileset: write a Godot 4 TileSet `.tres` from a Tiled tileset JSON/TSX, a tileset-gen /
autotile-gen meta JSON, or a plain image with --tile. Emits atlas tiles plus, when present:
physics collision polygons (Tiled per-tile objectgroups, or a tile-colliders / per-tile JSON via
`--colliders`), terrain sets (Tiled / tileset-wang wangsets, or `--wang`), and tile animations
(Tiled `tiles[].animation`, when the frames form a compact atlas grid — a Godot atlas-source
limit). Texture path is written as res://... (override with `--res`). The input is never
overwritten unless `--in-place`. Verified in official Godot 4.7.2.stable.official.ed1daf0bf.
"""
import argparse, os, json, math, sys, xml.etree.ElementTree as ET
from pathlib import Path as P

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

# Tiled wangid: [top, top-right, right, bottom-right, bottom, bottom-left, left, top-left]
WANG_TO_PEER = (
    "top_side", "top_right_corner", "right_side", "bottom_right_corner",
    "bottom_side", "bottom_left_corner", "left_side", "top_left_corner",
)
WANG_MODE = {"mixed": 0, "corner": 1, "edge": 2}


def fmt_num(x):
    x = float(x)
    if math.isfinite(x) and abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.6g}"


def fmt_color(rgba):
    r, g, b, a = rgba
    return f"Color({fmt_num(r)}, {fmt_num(g)}, {fmt_num(b)}, {fmt_num(a)})"


def parse_color(c, default=(0.290196, 0.560784, 0.235294, 1.0)):
    if not c:
        return default
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        a = float(c[3]) if len(c) > 3 else 1.0
        return (float(c[0]), float(c[1]), float(c[2]), a)
    s = str(c).strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) < 6:
            return default
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        a = int(h[6:8], 16) / 255.0 if len(h) >= 8 else 1.0
        return (r, g, b, a)
    return default


def atlas_xy(i, cols):
    return int(i) % cols, int(i) // cols


def tile_id(x, y, cols):
    return int(y) * cols + int(x)


def center_poly(points, tw, th):
    cx, cy = tw / 2.0, th / 2.0
    return [(float(x) - cx, float(y) - cy) for x, y in points]


def rect_poly(x, y, w, h, tw, th):
    return center_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], tw, th)


def ellipse_poly(x, y, w, h, tw, th, n=12):
    cx, cy, rx, ry = x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return center_poly(pts, tw, th)


def props_of(obj):
    p = obj.get("properties")
    out = {}
    if isinstance(p, list):
        for it in p:
            if isinstance(it, dict) and "name" in it:
                out[str(it["name"]).lower()] = it.get("value")
    elif isinstance(p, dict):
        out = {str(k).lower(): v for k, v in p.items()}
    return out


def is_one_way(obj):
    pr = props_of(obj)
    for k in ("oneway", "one_way", "one-way"):
        v = pr.get(k)
        if v in (True, 1, "true", "True", "1"):
            return True
    typ = (obj.get("type") or obj.get("class") or "").lower()
    return typ in ("oneway", "one_way", "platform")


def objects_to_polys(objects, tw, th, warn):
    out = []
    for obj in objects or []:
        if not isinstance(obj, dict):
            continue
        ox, oy = float(obj.get("x") or 0), float(obj.get("y") or 0)
        w, h = float(obj.get("width") or 0), float(obj.get("height") or 0)
        one = is_one_way(obj)
        if obj.get("polygon"):
            pts = [(ox + float(p.get("x", 0)), oy + float(p.get("y", 0))) for p in obj["polygon"]]
            out.append({"points": center_poly(pts, tw, th), "one_way": one})
        elif obj.get("polyline"):
            pts = [(ox + float(p.get("x", 0)), oy + float(p.get("y", 0))) for p in obj["polyline"]]
            if len(pts) >= 2 and pts[0] != pts[-1]:
                pts.append(pts[0])
            if len(pts) < 3:
                warn.append("skipped a polyline with fewer than 3 points")
                continue
            out.append({"points": center_poly(pts, tw, th), "one_way": one})
        elif obj.get("ellipse"):
            if w <= 0 or h <= 0:
                warn.append("skipped an ellipse with no size")
                continue
            out.append({"points": ellipse_poly(ox, oy, w, h, tw, th), "one_way": one})
        elif w > 0 and h > 0:
            out.append({"points": rect_poly(ox, oy, w, h, tw, th), "one_way": one})
        else:
            warn.append("skipped a collision object with no polygon or size")
    return out


def parse_tsx(path):
    root = ET.parse(path).getroot()
    if root.tag != "tileset":
        raise SystemExit(f"not a Tiled tileset: {path}")

    def _int(el, k, default=None):
        v = el.get(k)
        return default if v is None else int(v)

    t = {"name": root.get("name") or P(path).stem,
         "tilewidth": _int(root, "tilewidth", 0) or 0,
         "tileheight": _int(root, "tileheight", 0) or 0,
         "tilecount": _int(root, "tilecount", 0) or 0,
         "columns": _int(root, "columns", 0) or 0,
         "margin": _int(root, "margin", 0) or 0,
         "spacing": _int(root, "spacing", 0) or 0}
    im = root.find("image")
    if im is not None:
        t["image"] = im.get("source") or ""
        if im.get("width"):
            t["imagewidth"] = int(im.get("width"))
        if im.get("height"):
            t["imageheight"] = int(im.get("height"))
    tiles = []
    for tile in root.findall("tile"):
        rec = {"id": int(tile.get("id", 0))}
        anim = tile.find("animation")
        if anim is not None:
            rec["animation"] = [{"tileid": int(f.get("tileid", 0)), "duration": int(f.get("duration", 0))}
                                for f in anim.findall("frame")]
        og = tile.find("objectgroup")
        if og is not None:
            objects = []
            for o in og.findall("object"):
                obj = {"x": float(o.get("x") or 0), "y": float(o.get("y") or 0),
                       "width": float(o.get("width") or 0), "height": float(o.get("height") or 0)}
                if o.get("type"):
                    obj["type"] = o.get("type")
                if o.get("class"):
                    obj["class"] = o.get("class")
                if o.find("ellipse") is not None:
                    obj["ellipse"] = True
                poly = o.find("polygon")
                if poly is not None:
                    obj["polygon"] = _points(poly.get("points") or "")
                pl = o.find("polyline")
                if pl is not None:
                    obj["polyline"] = _points(pl.get("points") or "")
                pr = o.find("properties")
                if pr is not None:
                    obj["properties"] = [_tsx_prop(p) for p in pr.findall("property")]
                objects.append(obj)
            rec["objectgroup"] = {"objects": objects}
        tiles.append(rec)
    if tiles:
        t["tiles"] = tiles
    wangsets = []
    wroot = root.find("wangsets")
    if wroot is not None:
        for ws in wroot.findall("wangset"):
            rec = {"name": ws.get("name") or "terrain", "type": (ws.get("type") or "mixed").lower(), "colors": [], "wangtiles": []}
            for c in ws.findall("wangcolor"):
                rec["colors"].append({"name": c.get("name") or "terrain", "color": c.get("color") or "#4a8f3c"})
            for wt in ws.findall("wangtile"):
                wid = wt.get("wangid") or ""
                if "," in wid:
                    bits = [int(x) for x in wid.split(",") if x.strip() != ""]
                else:
                    # older Tiled packed hex
                    bits = []
                rec["wangtiles"].append({"tileid": int(wt.get("tileid", 0)), "wangid": bits})
            wangsets.append(rec)
    if wangsets:
        t["wangsets"] = wangsets
    return t


def _points(s):
    out = []
    for part in s.replace(";", " ").split():
        if "," not in part:
            continue
        a, b = part.split(",", 1)
        out.append({"x": float(a), "y": float(b)})
    return out


def _tsx_prop(el):
    typ = el.get("type") or "string"
    val = el.get("value")
    if typ == "bool":
        val = str(val).lower() in ("true", "1")
    elif typ in ("int", "float"):
        val = float(val) if typ == "float" else int(val)
    return {"name": el.get("name"), "type": typ, "value": val}


def load_spec(path, tile, columns, image, count):
    if path and path.lower().endswith((".png", ".webp", ".bmp")):
        from PIL import Image
        im = Image.open(path)
        tw, th = tile, tile
        cols = columns or max(1, im.width // tw)
        rows = max(1, im.height // th)
        return {"image": path, "tilewidth": tw, "tileheight": th, "columns": cols,
                "tilecount": count or cols * rows, "imagewidth": im.width, "imageheight": im.height,
                "name": P(path).stem, "tiles": [], "wangsets": [], "margin": 0, "spacing": 0}
    if not path:
        sys.exit("pass a tileset JSON, TSX, or an image")
    low = path.lower()
    if low.endswith((".tsx", ".xml")):
        meta = parse_tsx(path)
    else:
        meta = json.load(open(path, encoding="utf-8"))
        if meta.get("type") == "map":
            sys.exit(f"{path} looks like a map, not a tileset")
    image = image or meta.get("image") or (os.path.splitext(path)[0] + ".png")
    if meta.get("image") and not os.path.isabs(str(meta.get("image"))) and not os.path.isfile(image):
        cand = os.path.join(os.path.dirname(os.path.abspath(path)), str(meta.get("image")))
        if os.path.isfile(cand):
            image = cand
    tw = meta.get("tilewidth") or meta.get("tile") or tile
    th = meta.get("tileheight") or meta.get("tile") or tile
    cols = meta.get("columns") or columns
    n = meta.get("tilecount") or meta.get("count")
    iw, ih = meta.get("imagewidth"), meta.get("imageheight")
    if (cols is None or n is None or iw is None) and os.path.isfile(image):
        from PIL import Image
        im = Image.open(image)
        iw, ih = im.size
        cols = cols or max(1, iw // int(tw))
        n = n or cols * max(1, ih // int(th))
    cols = cols or 8
    n = n or cols
    return {"image": image, "tilewidth": int(tw), "tileheight": int(th), "columns": int(cols),
            "tilecount": int(n), "imagewidth": iw, "imageheight": ih,
            "name": meta.get("name") or P(path).stem,
            "tiles": list(meta.get("tiles") or []),
            "wangsets": list(meta.get("wangsets") or []),
            "margin": int(meta.get("margin") or 0), "spacing": int(meta.get("spacing") or 0)}


def res_path(image, res_root):
    if res_root:
        return res_root
    return "res://" + os.path.basename(image)


def fit_animation(ids, cols):
    if len(ids) < 2:
        return None
    coords = [atlas_xy(i, cols) for i in ids]
    x0, y0 = coords[0]
    n = len(ids)
    for ac in range(1, n + 1):
        expected = [(x0 + (i % ac), y0 + (i // ac)) for i in range(n)]
        if expected == coords:
            return ac
    return None


def tiles_by_id(tiles):
    out = {}
    for rec in tiles or []:
        if not isinstance(rec, dict):
            continue
        if "id" in rec:
            out[int(rec["id"])] = rec
        elif "tileid" in rec:
            out[int(rec["tileid"])] = rec
    return out


def animations_of(spec, warn):
    cols, n = spec["columns"], spec["tilecount"]
    out = {}  # origin id -> {columns, frames, speed, durations, cells}
    reserved = set()
    by = tiles_by_id(spec.get("tiles"))
    for tid, rec in by.items():
        frames = rec.get("animation") or []
        if len(frames) < 2:
            continue
        ids = [int(f.get("tileid", f.get("id", 0))) for f in frames]
        durs_ms = [int(f.get("duration") or 100) for f in frames]
        ac = fit_animation(ids, cols)
        if ac is None:
            warn.append(f"tile {tid} animation frames {ids} are not a compact atlas grid; skipped")
            continue
        cells = []
        x0, y0 = atlas_xy(ids[0], cols)
        for i in range(len(ids)):
            cells.append((x0 + (i % ac), y0 + (i // ac)))
        # Godot frame time = duration / speed seconds; pick speed so min 100ms → 1.0 at speed 10
        speed = 10.0
        durations = [max((ms / 1000.0) * speed, 0.01) for ms in durs_ms]
        origin = ids[0]
        out[origin] = {"columns": ac, "count": len(ids), "speed": speed, "durations": durations, "cells": cells}
        for i, cell in enumerate(cells):
            if i == 0:
                continue
            reserved.add(cell)
    return out, reserved


def collisions_from_tiles(spec, warn):
    tw, th = spec["tilewidth"], spec["tileheight"]
    out = {}
    for tid, rec in tiles_by_id(spec.get("tiles")).items():
        og = rec.get("objectgroup") or {}
        objects = og.get("objects") if isinstance(og, dict) else None
        if not objects:
            continue
        polys = objects_to_polys(objects, tw, th, warn)
        if polys:
            out[atlas_xy(tid, spec["columns"])] = polys
    return out


def collisions_from_colliders(path, spec, warn):
    data = json.load(open(path, encoding="utf-8"))
    tw, th = spec["tilewidth"], spec["tileheight"]
    cols, n = spec["columns"], spec["tilecount"]
    rows = max(1, math.ceil(n / cols))
    margin, spacing = spec.get("margin") or 0, spec.get("spacing") or 0
    out = {}

    def add(cell, polys):
        out.setdefault(cell, []).extend(polys)

    # full-tile boxes for a list of local ids
    solid = data.get("solid") or data.get("solid_ids") or data.get("ids")
    if solid and not data.get("rects") and not data.get("tiles") and not data.get("objects"):
        for tid in solid:
            add(atlas_xy(int(tid), cols), [{"points": rect_poly(0, 0, tw, th, tw, th), "one_way": False}])
        return out

    # per-tile dict: tiles[id] = {objectgroup|rects|polygons} or a list of objects
    tiles = data.get("tiles")
    if isinstance(tiles, dict) and not data.get("rects"):
        for k, rec in tiles.items():
            tid = int(k) if str(k).lstrip("-").isdigit() else None
            if tid is None and isinstance(rec, dict) and "id" in rec:
                tid = int(rec["id"])
            if tid is None:
                continue
            polys = []
            if isinstance(rec, list):
                polys = objects_to_polys(rec, tw, th, warn)
            elif isinstance(rec, dict):
                if rec.get("objectgroup") or rec.get("objects"):
                    objs = rec.get("objects") or (rec.get("objectgroup") or {}).get("objects") or []
                    polys = objects_to_polys(objs, tw, th, warn)
                for r in rec.get("rects") or []:
                    polys.append({"points": rect_poly(float(r.get("x", 0)), float(r.get("y", 0)),
                                                      float(r.get("w") or r.get("width") or tw),
                                                      float(r.get("h") or r.get("height") or th), tw, th),
                                  "one_way": bool(r.get("one_way") or r.get("oneway"))})
                for poly in rec.get("polygons") or []:
                    pts = [(float(p[0]), float(p[1])) if not isinstance(p, dict) else (float(p.get("x", 0)), float(p.get("y", 0))) for p in poly]
                    polys.append({"points": center_poly(pts, tw, th), "one_way": False})
            if polys:
                add(atlas_xy(tid, cols), polys)
        if out:
            return out

    # tile-colliders output (or a Tiled object layer) in tileset-sheet space
    rects = []
    if data.get("type") == "objectgroup" or "objects" in data:
        for o in data.get("objects") or []:
            rects.append({"x": float(o.get("x", 0)), "y": float(o.get("y", 0)),
                          "w": float(o.get("width") or o.get("w") or 0),
                          "h": float(o.get("height") or o.get("h") or 0),
                          "one_way": is_one_way(o)})
    for r in data.get("rects") or []:
        rects.append({"x": float(r.get("x", 0)), "y": float(r.get("y", 0)),
                      "w": float(r.get("w") or r.get("width") or 0),
                      "h": float(r.get("h") or r.get("height") or 0),
                      "one_way": bool(r.get("one_way") or r.get("oneway"))})
    if not rects:
        warn.append(f"no rects or per-tile colliders in {path}")
        return out
    for r in rects:
        rx, ry, rw, rh = r["x"], r["y"], r["w"], r["h"]
        if rw <= 0 or rh <= 0:
            continue
        hit = 0
        for cy in range(rows):
            for cx in range(cols):
                bx0 = margin + cx * (tw + spacing)
                by0 = margin + cy * (th + spacing)
                bx1, by1 = bx0 + tw, by0 + th
                ix0, iy0 = max(rx, bx0), max(ry, by0)
                ix1, iy1 = min(rx + rw, bx1), min(ry + rh, by1)
                if ix1 - ix0 > 0.5 and iy1 - iy0 > 0.5:
                    add((cx, cy), [{"points": rect_poly(ix0 - bx0, iy0 - by0, ix1 - ix0, iy1 - iy0, tw, th),
                                    "one_way": r.get("one_way", False)}])
                    hit += 1
        if not hit:
            warn.append(f"collider rect at {rx},{ry} {rw}x{rh} does not overlap the tileset sheet grid")
    return out


def terrains_of(spec, warn):
    """-> (sets, tile_terrain) where tile_terrain[cell] = {set, terrain, peering: {name: idx}}"""
    sets = []
    tile_t = {}
    cols = spec["columns"]
    for si, ws in enumerate(spec.get("wangsets") or []):
        typ = (ws.get("type") or "mixed").lower()
        mode = WANG_MODE.get(typ, 0)
        colors = list(ws.get("colors") or [])
        if not colors:
            colors = [{"name": ws.get("name") or "terrain", "color": "#4a8f3c"}]
        sets.append({
            "name": ws.get("name") or f"terrain_{si}",
            "mode": mode,
            "terrains": [{"name": c.get("name") or f"t{j}", "color": parse_color(c.get("color"))}
                         for j, c in enumerate(colors)],
        })
        for wt in ws.get("wangtiles") or []:
            tid = int(wt.get("tileid", wt.get("id", 0)))
            wangid = list(wt.get("wangid") or [])
            peering = {}
            used = set()
            for i, bit in enumerate(wangid[:8]):
                bit = int(bit)
                if bit <= 0:
                    continue
                # Tiled color index is 1-based
                terr = bit - 1
                if terr < 0 or terr >= len(colors):
                    warn.append(f"wang color index {bit} on tile {tid} is out of range")
                    continue
                peering[WANG_TO_PEER[i]] = terr
                used.add(terr)
            if not peering:
                continue
            # the tile's own terrain is the most common peering terrain (usually the only one)
            terrain = max(used, key=lambda t: sum(1 for v in peering.values() if v == t))
            tile_t[atlas_xy(tid, cols)] = {"set": si, "terrain": terrain, "peering": peering}
    return sets, tile_t


def tres(spec, res, collisions, terrains, tile_terrain, animations, reserved, resource_name="TileSet"):
    tw, th, cols, n = spec["tilewidth"], spec["tileheight"], spec["columns"], spec["tilecount"]
    has_phys = any(collisions.values())
    lines = [
        '[gd_resource type="TileSet" load_steps=3 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{res}" id="1_tex"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_0"]',
        'texture = ExtResource("1_tex")',
        f"texture_region_size = Vector2i({tw}, {th})",
    ]
    # write tiles in atlas order; skip cells reserved as non-origin animation frames
    for i in range(n):
        x, y = atlas_xy(i, cols)
        if (x, y) in reserved:
            continue
        anim = animations.get(i)
        if anim:
            lines.append(f"{x}:{y}/animation_columns = {anim['columns']}")
            lines.append(f"{x}:{y}/animation_speed = {fmt_num(anim['speed'])}")
            for fi, dur in enumerate(anim["durations"]):
                lines.append(f"{x}:{y}/animation_frame_{fi}/duration = {fmt_num(dur)}")
        lines.append(f"{x}:{y}/0 = 0")
        terr = tile_terrain.get((x, y))
        if terr:
            lines.append(f"{x}:{y}/0/terrain_set = {terr['set']}")
            lines.append(f"{x}:{y}/0/terrain = {terr['terrain']}")
        for pi, poly in enumerate(collisions.get((x, y), [])):
            pts = ", ".join(f"{fmt_num(px)}, {fmt_num(py)}" for px, py in poly["points"])
            lines.append(f"{x}:{y}/0/physics_layer_0/polygon_{pi}/points = PackedVector2Array({pts})")
            if poly.get("one_way"):
                lines.append(f"{x}:{y}/0/physics_layer_0/polygon_{pi}/one_way = true")
        if terr:
            for name, idx in terr["peering"].items():
                lines.append(f"{x}:{y}/0/terrains_peering_bit/{name} = {idx}")
    lines += ["", "[resource]"]
    if has_phys:
        lines.append("physics_layer_0/collision_layer = 1")
        lines.append("physics_layer_0/collision_mask = 1")
    lines.append(f"tile_size = Vector2i({tw}, {th})")
    for si, ts in enumerate(terrains):
        lines.append(f"terrain_set_{si}/mode = {ts['mode']}")
        for ti, terr in enumerate(ts["terrains"]):
            lines.append(f'terrain_set_{si}/terrain_{ti}/name = "{terr["name"]}"')
            lines.append(f"terrain_set_{si}/terrain_{ti}/color = {fmt_color(terr['color'])}")
    lines += ['sources/0 = SubResource("TileSetAtlasSource_0")', ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 TileSet .tres from a Tiled tileset or sheet, with optional collision, terrain and animation.")
    ap.add_argument("input", nargs="?", help="Tiled tileset JSON/TSX, tileset-gen meta JSON, or an image")
    ap.add_argument("-o", "--out", required=True, help="output .tres")
    ap.add_argument("--image", help="override texture path")
    ap.add_argument("--tile", type=int, default=16)
    ap.add_argument("--columns", type=int)
    ap.add_argument("--res", help="texture path written in the resource (default res://<basename>)")
    ap.add_argument("--colliders", help="tile-colliders JSON (sheet space), per-tile collision JSON, or a list of solid ids")
    ap.add_argument("--wang", help="tileset-wang / Tiled tileset JSON whose wangsets should be used")
    ap.add_argument("--no-collision", action="store_true")
    ap.add_argument("--no-terrain", action="store_true")
    ap.add_argument("--no-animation", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    srcs = [p for p in (a.input, a.colliders, a.wang) if p]
    safe_out.check_any(srcs, a.out, a.in_place)
    if a.json:
        safe_out.check_any(srcs, a.json, a.in_place)
    spec = load_spec(a.input, a.tile, a.columns, a.image, None)
    if a.image:
        spec["image"] = a.image
    if a.wang:
        extra = json.load(open(a.wang, encoding="utf-8")) if not a.wang.lower().endswith((".tsx", ".xml")) else parse_tsx(a.wang)
        if extra.get("wangsets"):
            spec["wangsets"] = list(extra["wangsets"])
        else:
            sys.exit(f"{a.wang} has no wangsets")
    warn = []
    animations, reserved = ({}, set()) if a.no_animation else animations_of(spec, warn)
    collisions = {} if a.no_collision else collisions_from_tiles(spec, warn)
    if a.colliders and not a.no_collision:
        more = collisions_from_colliders(a.colliders, spec, warn)
        for k, v in more.items():
            collisions.setdefault(k, []).extend(v)
    terrains, tile_terrain = ([], {}) if a.no_terrain else terrains_of(spec, warn)
    text = tres(spec, a.res or res_path(spec["image"], None), collisions, terrains, tile_terrain, animations, reserved)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(text)
    rec = {"tiles": spec["tilecount"], "width": spec["tilewidth"], "height": spec["tileheight"],
           "columns": spec["columns"], "collision_tiles": len(collisions),
           "terrain_sets": len(terrains), "terrain_tiles": len(tile_terrain),
           "animations": len(animations), "warn": warn, "out": a.out}
    bits = [f"{spec['tilecount']} tile(s), {spec['tilewidth']}x{spec['tileheight']}, {spec['columns']} col(s)"]
    if collisions:
        bits.append(f"{len(collisions)} collision")
    if terrains:
        bits.append(f"{len(terrains)} terrain set(s)")
    if animations:
        bits.append(f"{len(animations)} anim")
    print(", ".join(bits) + f" -> {a.out}")
    for w in warn:
        print("WARN", w)
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
