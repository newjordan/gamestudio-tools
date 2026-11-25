#!/usr/bin/env python3
"""hitbox-to-godot: write a Godot 4 Area2D scene from hitbox-gen JSON.

Each frame becomes an Area2D with one CollisionShape2D (aabb, circle or
capsule). A single-shape document (no `frames` map) is also accepted.
`--shape` selects which hitbox-gen shape to use (default aabb). The input
is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402


def load_frames(doc):
    if not isinstance(doc, dict):
        raise GstInputError("hitbox JSON is not an object")
    if isinstance(doc.get("frames"), dict) and doc["frames"]:
        return doc["frames"]
    if any(k in doc for k in ("aabb", "circle", "capsule")):
        return {"hitbox": doc}
    raise GstInputError("hitbox JSON has no frames")


def sanitize(name, used):
    raw = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(name or "frame")) or "frame"
    n, i = raw, 0
    while n in used:
        i += 1
        n = "%s_%d" % (raw, i)
    used.add(n)
    return n


def emit_shape(kind, rec, sub_i):
    if rec.get("empty"):
        return None, sub_i, []
    if kind == "aabb":
        box = rec.get("aabb") or {}
        w, h = float(box.get("w") or 0), float(box.get("h") or 0)
        if w <= 0 or h <= 0:
            return None, sub_i, []
        sid = "RectangleShape2D_%d" % sub_i
        sub = (sid, "RectangleShape2D", ["size = Vector2(%s, %s)" % (godot_text.num(w), godot_text.num(h))])
        pos = (float(box.get("x") or 0) + w / 2.0, float(box.get("y") or 0) + h / 2.0)
        return (sub, pos, 0.0), sub_i + 1, []
    if kind == "circle":
        c = rec.get("circle") or {}
        r = float(c.get("r") or 0)
        if r <= 0:
            return None, sub_i, []
        sid = "CircleShape2D_%d" % sub_i
        sub = (sid, "CircleShape2D", ["radius = %s" % godot_text.num(r)])
        pos = (float(c.get("cx") or 0), float(c.get("cy") or 0))
        return (sub, pos, 0.0), sub_i + 1, []
    if kind == "capsule":
        c = rec.get("capsule") or {}
        r = float(c.get("r") or 0)
        length = float(c.get("length") or 0)
        if r <= 0:
            return None, sub_i, []
        height = max(length + 2.0 * r, 2.0 * r)
        sid = "CapsuleShape2D_%d" % sub_i
        sub = (sid, "CapsuleShape2D", ["radius = %s" % godot_text.num(r), "height = %s" % godot_text.num(height)])
        pos = (float(c.get("cx") or 0), float(c.get("cy") or 0))
        rot = math.pi / 2.0 if c.get("axis") == "x" else 0.0
        return (sub, pos, rot), sub_i + 1, []
    raise GstInputError("unknown shape %r" % kind)


def write_scene(path, frames, kind):
    sub_defs, blocks, used = [], [], set()
    sub_i, kept = 0, 0
    for fname, rec in frames.items():
        if not isinstance(rec, dict):
            raise GstInputError("hitbox frame %r is not an object" % fname)
        emitted, sub_i, _ = emit_shape(kind, rec, sub_i)
        if emitted is None:
            continue
        sub, pos, rot = emitted
        sub_defs.append(sub)
        name = sanitize(os.path.splitext(str(fname))[0], used)
        blocks.append('[node name="%s" type="Area2D" parent="."]' % name)
        blocks.append("")
        blocks.append('[node name="Shape" type="CollisionShape2D" parent="%s"]' % name)
        blocks.append("position = Vector2(%s, %s)" % (godot_text.num(pos[0]), godot_text.num(pos[1])))
        if rot:
            blocks.append("rotation = %s" % godot_text.num(rot))
        blocks.append('shape = SubResource("%s")' % sub[0])
        blocks.append("")
        kept += 1
    if not kept:
        raise GstInputError("no non-empty %s hitboxes to write" % kind)
    load_steps = 1 + len(sub_defs)
    lines = ['[gd_scene load_steps=%d format=3]' % load_steps, ""]
    for sid, typ, props in sub_defs:
        lines.append('[sub_resource type="%s" id="%s"]' % (typ, sid))
        lines.extend(props)
        lines.append("")
    lines.append('[node name="Hitboxes" type="Node2D"]')
    lines.append("")
    lines.extend(blocks)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return kept


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 Area2D scene from hitbox-gen JSON.")
    ap.add_argument("json_in", metavar="json")
    ap.add_argument("-o", "--out", required=True, help="output .tscn")
    ap.add_argument("--shape", choices=("aabb", "circle", "capsule"), default="aabb")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.json_in, a.out, a.in_place)
    if a.json:
        safe_out.check(a.json_in, a.json, a.in_place)
    doc = gst_read.require_object(gst_read.load_json(a.json_in, "hitbox JSON"), "hitbox JSON")
    if doc.get("normalized"):
        raise GstInputError("normalized hitbox JSON is not supported (re-run hitbox-gen without --normalize)")
    frames = load_frames(doc)
    n = write_scene(a.out, frames, a.shape)
    rec = {"out": a.out, "frames": n, "shape": a.shape}
    print("%d %s hitbox(es) -> %s" % (n, a.shape, a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
