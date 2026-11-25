#!/usr/bin/env python3
"""map-objects-to-godot: write a Godot 4 Node2D scene from Tiled object layers.

Points become Marker2D nodes; rectangles, ellipses and polygons become Area2D
(or StaticBody2D with --static) with CollisionShape2D / CollisionPolygon2D.
Custom properties and the Tiled type are stored as metadata. Tile objects (a
GID) become Sprite2D nodes with an atlas region (`region_rect`) and flip flags
(`flip_h` / `flip_v`; a diagonal flip is a quarter turn plus a flip), honouring
the tileset's `objectalignment` and `tileoffset`; `--no-sprites` keeps them as
metadata only. Isometric maps are projected like Tiled's isometric renderer
(rectangles, ellipses, polygons and polylines are projected into screen space).
Staggered and hexagonal maps already store object coordinates as screen pixels
(Tiled's HexagonalRenderer inherits the orthogonal identity for
pixel-to-screen); `Projection.tile_to_screen` maps the tile grid the same way
Tiled does, including staggeraxis, staggerindex and hexsidelength. Polylines
become a Line2D (open, not a filled polygon) plus a CollisionPolygon2D with
build_mode = 1 (segments). Group layers are walked. The input is never
overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-to-godot"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402
import map_to_godot  # noqa: E402


def props_of(obj):
    p = obj.get("properties")
    out = {}
    if isinstance(p, dict):
        return {str(k): v for k, v in p.items()}
    if isinstance(p, list):
        for it in p:
            if isinstance(it, dict) and it.get("name") not in (None, ""):
                out[str(it["name"])] = it.get("value")
    return out


def sanitize(name, used):
    raw = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(name or "object")) or "object"
    n, i = raw, 0
    while n in used:
        i += 1
        n = "%s_%d" % (raw, i)
    used.add(n)
    return n


def collect(doc):
    layers = []
    def walk(items, prefix=""):
        for l in items or []:
            typ = l.get("type")
            name = prefix + (l.get("name") or "objects")
            if typ == "group":
                walk(l.get("layers") or [], name + "/")
                continue
            if typ != "objectgroup":
                continue
            layers.append({"name": name, "objects": list(l.get("objects") or []), "visible": l.get("visible", True)})
    walk(doc.get("layers") or [])
    return layers


def meta_lines(indent, pairs):
    lines = []
    for k, v in pairs:
        if v is None:
            continue
        lines.append('%smetadata/%s = %s' % (indent, k, godot_text.literal(v)))
    return lines


def shape_kind(obj):
    if obj.get("polygon"):
        return "polygon"
    if obj.get("polyline"):
        return "polyline"
    if obj.get("ellipse"):
        return "ellipse"
    if obj.get("point") or (float(obj.get("width") or 0) == 0 and float(obj.get("height") or 0) == 0 and not obj.get("gid")):
        return "point"
    return "rect"


ANCHORS = {
    "topleft": (0.0, 0.0), "top": (0.5, 0.0), "topright": (1.0, 0.0),
    "left": (0.0, 0.5), "center": (0.5, 0.5), "right": (1.0, 0.5),
    "bottomleft": (0.0, 1.0), "bottom": (0.5, 1.0), "bottomright": (1.0, 1.0),
}
ELLIPSE_POINTS = 16


class Projection:
    """Object-space -> Godot scene space for one Tiled orientation.

    Orthogonal maps store object coordinates as plain pixels. Isometric
    (diamond) maps store them in logical units where one tile is tileheight
    wide, projected like Tiled's IsometricRenderer. Staggered and hexagonal
    maps also store object coordinates as screen pixels: Tiled's
    HexagonalRenderer does not override pixelToScreenCoords, so the identity
    inherited from OrthogonalRenderer is used. Applying the diamond formula
    to those maps would put objects in the wrong place.

    tile_to_screen maps *tile* coordinates the way Tiled's
    HexagonalRenderer / StaggeredRenderer does (staggeraxis, staggerindex,
    hexsidelength). Object positions must go through point(), not this.
    """

    def __init__(self, doc):
        self.orientation = str(doc.get("orientation") or "orthogonal")
        self.tw = float(doc.get("tilewidth") or 16)
        self.th = float(doc.get("tileheight") or 16)
        self.map_h = float(doc.get("height") or 0)
        self.iso = self.orientation == "isometric"
        self.stagger = self.orientation in ("staggered", "hexagonal")
        axis = str(doc.get("staggeraxis") or "y").lower()
        self.stagger_axis = "x" if axis == "x" else "y"
        idx = str(doc.get("staggerindex") or "odd").lower()
        self.stagger_index = "even" if idx == "even" else "odd"
        try:
            self.hex_side = float(doc.get("hexsidelength") or 0)
        except (TypeError, ValueError):
            self.hex_side = 0.0

    def point(self, x, y):
        if not self.iso:
            return float(x), float(y)
        tx, ty = float(x) / self.th, float(y) / self.th
        return (tx - ty) * self.tw / 2.0 + self.map_h * self.tw / 2.0, (tx + ty) * self.th / 2.0

    def delta(self, dx, dy):
        if not self.iso:
            return float(dx), float(dy)
        return (dx - dy) * (self.tw / 2.0) / self.th, (dx + dy) / 2.0

    def tile_to_screen(self, tx, ty):
        """Screen position of a tile coordinate, matching Tiled's tileToScreenCoords."""
        if self.iso:
            return self.point(float(tx) * self.th, float(ty) * self.th)
        if not self.stagger:
            return float(tx) * self.tw, float(ty) * self.th
        tw, th = int(self.tw), int(self.th)
        hex_side = int(self.hex_side) if self.orientation == "hexagonal" else 0
        side_x = hex_side if self.stagger_axis == "x" else 0
        side_y = hex_side if self.stagger_axis == "y" else 0
        side_offset_x = (tw - side_x) // 2
        side_offset_y = (th - side_y) // 2
        column_width = side_offset_x + side_x
        row_height = side_offset_y + side_y
        tile_w = column_width + side_offset_x
        tile_h = row_height + side_offset_y
        stagger_even = self.stagger_index == "even"
        tile_x, tile_y = float(tx), float(ty)
        if self.stagger_axis == "x":
            pixel_y = tile_y * (tile_h + side_y)
            if ((int(tile_x) & 1) == 1) != stagger_even:
                pixel_y += row_height
            pixel_x = tile_x * column_width
        else:
            pixel_x = tile_x * (tile_w + side_x)
            if ((int(tile_y) & 1) == 1) != stagger_even:
                pixel_x += column_width
            pixel_y = tile_y * row_height
        return float(pixel_x), float(pixel_y)


def default_anchor(tileset, proj):
    name = (tileset or {}).get("objectalignment") or "unspecified"
    if name in ANCHORS:
        return ANCHORS[name]
    return (0.5, 1.0) if proj.iso else (0.0, 1.0)


def _rot(rad, x, y):
    c, s = math.cos(rad), math.sin(rad)
    return c * x - s * y, s * x + c * y


def tile_flip_matrix(flags):
    """2x2 map of the unit square for Tiled flip flags (diagonal, then H, then V)."""
    def f(u, v):
        if flags & map_to_godot.FLIP_D:
            u, v = v, u
        if flags & map_to_godot.FLIP_H:
            u = 1.0 - u
        if flags & map_to_godot.FLIP_V:
            v = 1.0 - v
        return u, v
    o = f(0.0, 0.0)
    a, b = f(1.0, 0.0), f(0.0, 1.0)
    return (a[0] - o[0], b[0] - o[0], a[1] - o[1], b[1] - o[1]), o


def sprite_transform(flags, w, h, tw, th, rot_deg):
    """Decompose a tile object into Sprite2D flips, scale and rotation.

    Returns (flip_h, flip_v, scale_x, scale_y, extra_rotation_radians).
    The extra rotation is 0 or +pi/2 (a diagonal flip is a quarter turn plus a flip).
    """
    (uu, uv, vu, vv), _ = tile_flip_matrix(flags)
    # Mbox maps region pixels to box pixels
    m = ((uu * w / tw, uv * w / th), (vu * h / tw, vv * h / th))
    for k in (0, 1):
        for fh in (0, 1):
            for fv in (0, 1):
                fx, fy = (-1.0 if fh else 1.0), (-1.0 if fv else 1.0)
                a = (m[0][0] * fx, m[0][1] * fy, m[1][0] * fx, m[1][1] * fy)  # M * F
                eps = 1e-9
                if k == 0 and abs(a[1]) < eps and abs(a[2]) < eps and a[0] > eps and a[3] > eps:
                    return bool(fh), bool(fv), a[0], a[3], 0.0
                if k == 1 and abs(a[0]) < eps and abs(a[3]) < eps and a[2] > eps and a[1] < -eps:
                    return bool(fh), bool(fv), a[2], -a[1], math.pi / 2.0
    return False, False, w / tw, h / th, 0.0


def _columns(ts):
    cols = int(ts.get("columns") or 0)
    if cols <= 0:
        tw, iw = int(ts.get("tilewidth") or 0), int(ts.get("imagewidth") or 0)
        cols = max(1, iw // tw) if tw > 0 and iw > 0 else 1
    return cols


def _cell(ts, local):
    """(image, (x, y, w, h), collection?) for tile id `local` of a tileset, or None."""
    for t in ts.get("tiles") or []:
        if isinstance(t, dict) and t.get("id") == local and t.get("image"):
            iw, ih = int(t.get("imagewidth") or ts.get("tilewidth") or 16), int(t.get("imageheight") or ts.get("tileheight") or 16)
            return t["image"], (0, 0, iw, ih), True
    if not ts.get("image") or local < 0:
        return None
    tw, th = int(ts.get("tilewidth") or 0), int(ts.get("tileheight") or 0)
    if tw <= 0 or th <= 0:
        return None
    count = int(ts.get("tilecount") or 0)
    if count > 0 and local >= count:      # past the end of this tileset: not a real tile
        return None
    cols = _columns(ts)
    margin, spacing = int(ts.get("margin") or 0), int(ts.get("spacing") or 0)
    return ts["image"], (margin + (local % cols) * (tw + spacing), margin + (local // cols) * (th + spacing), tw, th), False


MAX_ANIM_FRAMES = 512


def _animation(ts, local):
    """[(image, region, duration_ms)] for an animated tile, or None when it has no usable animation."""
    for t in ts.get("tiles") or []:
        if isinstance(t, dict) and t.get("id") == local and isinstance(t.get("animation"), list) and t["animation"]:
            frames = []
            for f in t["animation"][:MAX_ANIM_FRAMES]:
                if not isinstance(f, dict):
                    return None
                try:
                    tid, dur = int(f.get("tileid")), int(f.get("duration"))
                except (TypeError, ValueError):
                    return None
                cell = _cell(ts, tid)
                if cell is None or dur <= 0:
                    return None
                frames.append((cell[0], cell[1], dur))
            return frames if len(frames) > 1 else None
    return None


def tile_info(gid, tilesets):
    """Return dict(image, region (x, y, w, h), flags, tileset, collection, animation) or None."""
    rec = map_to_godot.gid_to_cell(gid, tilesets)
    if rec is None:
        return None
    sid, ax, ay, flags = rec
    ts = tilesets[sid]
    local = (gid & map_to_godot.GID_MASK) - int(ts.get("firstgid") or 1)
    cell = _cell(ts, local)
    if cell is None:
        return None
    image, region, collection = cell
    return {"image": image, "region": region, "flags": flags, "tileset": ts, "collection": collection,
            "animation": _animation(ts, local), "key": (sid, local)}


def _meta_pairs(obj):
    pairs = []
    typ = obj.get("type") or obj.get("class") or ""
    if typ:
        pairs.append(("tiled_type", typ))
    if obj.get("gid"):
        pairs.append(("gid", int(obj["gid"]) & map_to_godot.GID_MASK))
    if obj.get("id") is not None:
        try:
            pairs.append(("tiled_id", int(obj["id"])))
        except (TypeError, ValueError):
            pass
    for k, v in props_of(obj).items():
        key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(k)) or "prop"
        pairs.append((key, v))
    return pairs


def _num(x):
    return godot_text.num(round(float(x), 6))


def _poly_line(pts):
    return ", ".join("%s, %s" % (_num(a), _num(b)) for a, b in pts)


def _corners(obj, kind):
    src = obj.get("polygon") if kind == "polygon" else obj.get("polyline") if kind == "polyline" else []
    pts = []
    for q in src or []:
        if not isinstance(q, dict):
            raise GstInputError("%s point is not an object" % kind)
        pts.append((float(q.get("x") or 0), float(q.get("y") or 0)))
    return pts


def _append_polyline(block, lname, name, pts, line_width, stats):
    if len(pts) < 2:
        raise GstInputError("polyline needs at least two points")
    packed = _poly_line(pts)
    block.append('[node name="Line" type="Line2D" parent="%s/%s"]' % (lname, name))
    block.append("points = PackedVector2Array(%s)" % packed)
    block.append("width = %s" % _num(line_width))
    block.append("closed = false")
    block.append("")
    block.append('[node name="Shape" type="CollisionPolygon2D" parent="%s/%s"]' % (lname, name))
    block.append("polygon = PackedVector2Array(%s)" % packed)
    block.append("build_mode = 1")
    block.append("")
    stats["polygons"] += 1
    stats["polylines"] += 1


def _ellipse_pts(w, h):
    return [(w / 2.0 + (w / 2.0) * math.cos(2 * math.pi * i / ELLIPSE_POINTS),
             h / 2.0 + (h / 2.0) * math.sin(2 * math.pi * i / ELLIPSE_POINTS)) for i in range(ELLIPSE_POINTS)]


def write_scene(path, layers, static, doc=None, res_prefix="res://", sprites=True, animate=True, line_width=2.0):
    doc = doc or {}
    proj = Projection(doc)
    tilesets = doc.get("tilesets") or []
    sub_defs = []   # (id, type, prop_lines)
    ext_defs = []   # (res path, id)
    ext_ids = {}
    node_blocks = []
    used_layer = set()
    sub_i = 0
    stats = {"objects": 0, "sprites": 0, "unknown_gids": 0, "diagonal_sprites": 0, "polygons": 0, "polylines": 0, "animated_sprites": 0}
    atlas_ids, frames_ids = {}, {}

    def texture_id(image):
        base = os.path.basename(str(image).replace("\\", "/"))
        res = godot_text.res_path(res_prefix, base)
        if res not in ext_ids:
            ext_ids[res] = "tex_%d" % (len(ext_ids) + 1)
            ext_defs.append((res, ext_ids[res]))
        return ext_ids[res]

    def frames_id(info):
        """SpriteFrames sub-resource (AtlasTexture frames) for an animated tile, shared by every object using it."""
        nonlocal sub_i
        key = info["key"]
        if key in frames_ids:
            return frames_ids[key]
        import math as _m
        durs = [d for _, _, d in info["animation"]]
        g = 0
        for d in durs:
            g = _m.gcd(g, d)
        entries = []
        for image, region, dur in info["animation"]:
            akey = (image, tuple(region))
            if akey not in atlas_ids:
                aid = "AtlasTexture_%d" % sub_i
                sub_i += 1
                sub_defs.append((aid, "AtlasTexture", ['atlas = ExtResource("%s")' % texture_id(image),
                                                       "region = Rect2(%s, %s, %s, %s)" % tuple(_num(v) for v in region)]))
                atlas_ids[akey] = aid
            entries.append('{ "duration": %s, "texture": SubResource("%s") }' % (_num(dur / float(g)), atlas_ids[akey]))
        sid = "SpriteFrames_%d" % sub_i
        sub_i += 1
        sub_defs.append((sid, "SpriteFrames", ['animations = [{ "frames": [%s], "loop": true, "name": &"default", "speed": %s }]'
                                               % (", ".join(entries), _num(1000.0 / g))]))
        frames_ids[key] = sid
        return sid

    for layer in layers:
        lname = sanitize(layer["name"].replace("/", "_") or "Layer", used_layer)
        lblock = ['[node name="%s" type="Node2D" parent="."]' % lname]
        if layer.get("visible") is False:
            lblock.append("visible = false")
        lblock.append("")
        node_blocks.append(lblock)
        used = set()
        for obj in layer["objects"]:
            stats["objects"] += 1
            kind = shape_kind(obj)
            gid = int(obj.get("gid") or 0)
            name = sanitize(obj.get("name") or ("gid_%s" % (gid & map_to_godot.GID_MASK) if gid else "object"), used)
            x, y = float(obj.get("x") or 0), float(obj.get("y") or 0)
            w, h = float(obj.get("width") or 0), float(obj.get("height") or 0)
            rot = float(obj.get("rotation") or 0)
            px, py = proj.point(x, y)
            body = "StaticBody2D" if static else "Area2D"
            block = []
            pairs = _meta_pairs(obj)
            info = tile_info(gid, tilesets) if (gid and sprites) else None
            if gid and sprites and info is None:
                stats["unknown_gids"] += 1
            if info is not None and info.get("animation") and not animate:      # still image: the animation's first frame
                info = dict(info, image=info["animation"][0][0], region=info["animation"][0][1])
            if info is not None:
                rx, ry, rw, rh = info["region"]
                if w <= 0:
                    w = float(rw)
                if h <= 0:
                    h = float(rh)
                ax, ay = default_anchor(info["tileset"], proj)
                off = info["tileset"].get("tileoffset") or {}
                ox = float(off.get("x") or 0) - ax * w
                oy = float(off.get("y") or 0) - ay * h
                fh, fv, sx, sy, extra = sprite_transform(info["flags"], w, h, float(rw), float(rh), rot)
                rad = math.radians(rot)
                # position of the sprite's local origin = image of the box corner it starts at
                if extra:   # quarter turn about the local origin: origin sits at the box's top-right in box space
                    corner = (ox + w, oy)
                else:
                    corner = (ox, oy)
                cx, cy = _rot(rad, corner[0], corner[1])
                animated = bool(animate and info.get("animation"))
                block.append('[node name="%s" type="%s" parent="%s"]' % (name, "AnimatedSprite2D" if animated else "Sprite2D", lname))
                block.append("position = Vector2(%s, %s)" % (_num(px + cx), _num(py + cy)))
                if rad + extra:
                    block.append("rotation = %s" % _num(rad + extra))
                if abs(sx - 1.0) > 1e-9 or abs(sy - 1.0) > 1e-9:
                    block.append("scale = Vector2(%s, %s)" % (_num(sx), _num(sy)))
                if animated:
                    block.append('sprite_frames = SubResource("%s")' % frames_id(info))
                    block.append('animation = &"default"')
                    block.append('autoplay = "default"')
                else:
                    block.append('texture = ExtResource("%s")' % texture_id(info["image"]))
                block.append("centered = false")
                if fh:
                    block.append("flip_h = true")
                if fv:
                    block.append("flip_v = true")
                if not animated:
                    block.append("region_enabled = true")
                    block.append("region_rect = Rect2(%s, %s, %s, %s)" % (_num(rx), _num(ry), _num(rw), _num(rh)))
                block.extend(meta_lines("", pairs))
                block.append("")
                node_blocks.append(block)
                stats["sprites"] += 1
                if animated:
                    stats["animated_sprites"] += 1
                if info["flags"] & map_to_godot.FLIP_D:
                    stats["diagonal_sprites"] += 1
                continue
            if kind == "point" or gid:     # a tile object without a usable sprite is a marker carrying its GID
                block.append('[node name="%s" type="Marker2D" parent="%s"]' % (name, lname))
                block.append("position = Vector2(%s, %s)" % (_num(px), _num(py)))
                if rot and not proj.iso:
                    block.append("rotation = %s" % _num(math.radians(rot)))
                block.extend(meta_lines("", pairs))
                block.append("")
                node_blocks.append(block)
                continue
            block.append('[node name="%s" type="%s" parent="%s"]' % (name, body, lname))
            block.append("position = Vector2(%s, %s)" % (_num(px), _num(py)))
            if rot and not proj.iso:
                block.append("rotation = %s" % _num(math.radians(rot)))
            block.extend(meta_lines("", pairs))
            block.append("")
            poly_pts = None   # screen-space polygon relative to the node, for iso or polygons
            if proj.iso and kind in ("rect", "ellipse", "polygon", "polyline"):
                rad = math.radians(rot)
                if kind == "rect":
                    local = [(0, 0), (w, 0), (w, h), (0, h)]
                elif kind == "ellipse":
                    local = _ellipse_pts(w, h)
                else:
                    local = _corners(obj, kind)
                poly_pts = [proj.delta(*_rot(rad, a, b)) for a, b in local]
            if poly_pts is not None and kind == "polyline":
                _append_polyline(block, lname, name, poly_pts, line_width, stats)
            elif poly_pts is not None:
                block.append('[node name="Shape" type="CollisionPolygon2D" parent="%s/%s"]' % (lname, name))
                block.append("polygon = PackedVector2Array(%s)" % _poly_line(poly_pts))
                block.append("")
                stats["polygons"] += 1
            elif kind == "rect":
                sid = "RectangleShape2D_%d" % sub_i
                sub_i += 1
                sub_defs.append((sid, "RectangleShape2D", ["size = Vector2(%s, %s)" % (godot_text.num(w), godot_text.num(h))]))
                block.append('[node name="Shape" type="CollisionShape2D" parent="%s/%s"]' % (lname, name))
                block.append("position = Vector2(%s, %s)" % (godot_text.num(w / 2.0), godot_text.num(h / 2.0)))
                block.append('shape = SubResource("%s")' % sid)
                block.append("")
            elif kind == "ellipse":
                if abs(w - h) < 1e-6:
                    sid = "CircleShape2D_%d" % sub_i
                    sub_i += 1
                    sub_defs.append((sid, "CircleShape2D", ["radius = %s" % godot_text.num(max(w, 0.0) / 2.0)]))
                    extra_rot = 0.0
                else:
                    if h >= w:
                        r, height, extra_rot = w / 2.0, h, 0.0
                    else:
                        r, height, extra_rot = h / 2.0, w, math.pi / 2.0
                    sid = "CapsuleShape2D_%d" % sub_i
                    sub_i += 1
                    sub_defs.append((sid, "CapsuleShape2D", [
                        "radius = %s" % godot_text.num(r),
                        "height = %s" % godot_text.num(max(height, 2.0 * r)),
                    ]))
                block.append('[node name="Shape" type="CollisionShape2D" parent="%s/%s"]' % (lname, name))
                block.append("position = Vector2(%s, %s)" % (godot_text.num(w / 2.0), godot_text.num(h / 2.0)))
                if extra_rot:
                    block.append("rotation = %s" % godot_text.num(extra_rot))
                block.append('shape = SubResource("%s")' % sid)
                block.append("")
            elif kind == "polyline":
                _append_polyline(block, lname, name, _corners(obj, "polyline"), line_width, stats)
            elif kind == "polygon":
                pts = _corners(obj, "polygon")
                packed = _poly_line(pts)
                block.append('[node name="Shape" type="CollisionPolygon2D" parent="%s/%s"]' % (lname, name))
                block.append("polygon = PackedVector2Array(%s)" % packed)
                block.append("")
                stats["polygons"] += 1
            node_blocks.append(block)
    load_steps = 1 + len(sub_defs) + len(ext_defs)
    lines = ['[gd_scene load_steps=%d format=3]' % load_steps, ""]
    for res, eid in ext_defs:
        lines.append('[ext_resource type="Texture2D" path="%s" id="%s"]' % (res, eid))
    if ext_defs:
        lines.append("")
    for sid, typ, props in sub_defs:
        lines.append('[sub_resource type="%s" id="%s"]' % (typ, sid))
        lines.extend(props)
        lines.append("")
    lines.append('[node name="MapObjects" type="Node2D"]')
    if proj.orientation != "orthogonal":
        lines.append('metadata/orientation = "%s"' % proj.orientation)
        if proj.stagger:
            lines.append('metadata/staggeraxis = "%s"' % proj.stagger_axis)
            lines.append('metadata/staggerindex = "%s"' % proj.stagger_index)
            if proj.orientation == "hexagonal":
                lines.append("metadata/hexsidelength = %s" % _num(proj.hex_side))
    lines.append("")
    for b in node_blocks:
        lines.extend(b)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    stats.update({"layers": len(layers), "shapes": len(sub_defs) + stats["polygons"], "textures": [r for r, _ in ext_defs],
                  "orientation": proj.orientation, "staggeraxis": proj.stagger_axis if proj.stagger else None,
                  "staggerindex": proj.stagger_index if proj.stagger else None,
                  "hexsidelength": proj.hex_side if proj.orientation == "hexagonal" else None})
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 scene from Tiled object layers.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True, help="output .tscn")
    ap.add_argument("--static", action="store_true", help="use StaticBody2D instead of Area2D for shaped objects")
    ap.add_argument("--res", default="res://", help="res:// folder for tileset textures used by Sprite2D (default res://)")
    ap.add_argument("--no-animation", action="store_true",
                    help="animated tiles become a plain Sprite2D showing their first frame")
    ap.add_argument("--no-sprites", action="store_true", help="do not attach Sprite2D to tile objects (GID stays as metadata)")
    ap.add_argument("--line-width", type=float, default=2.0,
                    help="Line2D width in pixels for polylines (default 2)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.line_width <= 0:
        raise GstInputError("--line-width must be positive")
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    doc = map_to_godot.load_map(a.map)
    try:
        layers = collect(doc)
        if not layers or not any(l["objects"] for l in layers):
            raise GstInputError("Tiled map has no objects")
        st = write_scene(a.out, layers, a.static, doc, a.res, not a.no_sprites, not a.no_animation, a.line_width)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as e:
        raise GstInputError("map has an unusable value (%s: %s)" % (type(e).__name__, e)) from e
    rec = {"out": a.out, "objects": st["objects"], "layers": st["layers"], "shapes": st["shapes"], "static": a.static,
           "sprites": st["sprites"], "animated_sprites": st["animated_sprites"], "diagonal_sprites": st["diagonal_sprites"], "unknown_gids": st["unknown_gids"],
           "textures": st["textures"], "orientation": st["orientation"], "polylines": st["polylines"],
           "staggeraxis": st.get("staggeraxis"), "staggerindex": st.get("staggerindex"),
           "hexsidelength": st.get("hexsidelength")}
    msg = "%d object(s) in %d layer(s) -> %s" % (st["objects"], st["layers"], a.out)
    if st["sprites"]:
        msg += " (%d sprite(s)%s)" % (st["sprites"], (", %d animated" % st["animated_sprites"]) if st["animated_sprites"] else "")
    print(msg)
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
