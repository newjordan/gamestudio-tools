#!/usr/bin/env python3
"""tile-colliders-to-godot: write a Godot 4 StaticBody2D scene from tile-colliders JSON.

Accepts the kit's `{"rects":[{"x","y","w","h"}, ...]}` layout or a Tiled object
layer (`{"objects":[{"x","y","width","height"}, ...]}`). Each rectangle becomes
a CollisionShape2D whose position is the rectangle centre (Godot shape origin).
The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402


def load_rects(doc):
    if not isinstance(doc, dict):
        raise GstInputError("collider JSON is not an object")
    if isinstance(doc.get("rects"), list):
        out = []
        for r in doc["rects"]:
            if not isinstance(r, dict):
                raise GstInputError("collider rect is not an object")
            out.append((float(r.get("x") or 0), float(r.get("y") or 0),
                        float(r.get("w") or r.get("width") or 0),
                        float(r.get("h") or r.get("height") or 0)))
        return out
    if isinstance(doc.get("objects"), list):
        out = []
        for r in doc["objects"]:
            if not isinstance(r, dict):
                raise GstInputError("collider object is not an object")
            out.append((float(r.get("x") or 0), float(r.get("y") or 0),
                        float(r.get("width") or r.get("w") or 0),
                        float(r.get("height") or r.get("h") or 0)))
        return out
    raise GstInputError("collider JSON has no rects or objects")


def write_scene(path, rects):
    kept = [(x, y, w, h) for x, y, w, h in rects if w > 0 and h > 0]
    if not kept:
        raise GstInputError("no positive-size collider rectangles")
    lines = ['[gd_scene load_steps=%d format=3]' % (1 + len(kept)), ""]
    for i, (x, y, w, h) in enumerate(kept):
        lines.append('[sub_resource type="RectangleShape2D" id="RectangleShape2D_%d"]' % i)
        lines.append("size = Vector2(%s, %s)" % (godot_text.num(w), godot_text.num(h)))
        lines.append("")
    lines.append('[node name="Colliders" type="StaticBody2D"]')
    lines.append("")
    for i, (x, y, w, h) in enumerate(kept):
        lines.append('[node name="R%d" type="CollisionShape2D" parent="."]' % i)
        lines.append("position = Vector2(%s, %s)" % (godot_text.num(x + w / 2.0), godot_text.num(y + h / 2.0)))
        lines.append('shape = SubResource("RectangleShape2D_%d")' % i)
        lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return len(kept)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 StaticBody2D scene from tile-colliders JSON.")
    ap.add_argument("json_in", metavar="json")
    ap.add_argument("-o", "--out", required=True, help="output .tscn")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.json_in, a.out, a.in_place)
    if a.json:
        safe_out.check(a.json_in, a.json, a.in_place)
    doc = gst_read.require_object(gst_read.load_json(a.json_in, "collider JSON"), "collider JSON")
    n = write_scene(a.out, load_rects(doc))
    rec = {"out": a.out, "rects": n}
    print("%d collider rectangle(s) -> %s" % (n, a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
