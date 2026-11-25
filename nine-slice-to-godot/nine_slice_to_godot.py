#!/usr/bin/env python3
"""nine-slice-to-godot: write a Godot 4 StyleBoxTexture `.tres` from an image and insets.

`--insets L,T,R,B` (or `--center X,Y,W,H`, same meaning as nine-slice) become
`texture_margin_*` on a StyleBoxTexture that ExtResource's the PNG. The image
itself is not copied. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nine-slice"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402


def parse_insets(image_w, image_h, insets=None, center=None):
    if insets and center:
        raise GstInputError("use --insets or --center, not both")
    if insets:
        parts = [p.strip() for p in insets.split(",")]
        if len(parts) != 4:
            raise GstInputError("--insets must be L,T,R,B")
        try:
            l, t, r, b = (float(p) for p in parts)
        except ValueError as e:
            raise GstInputError("--insets must be four numbers") from e
        return l, t, r, b
    if center:
        parts = [p.strip() for p in center.split(",")]
        if len(parts) != 4:
            raise GstInputError("--center must be X,Y,W,H")
        try:
            x, y, w, h = (float(p) for p in parts)
        except ValueError as e:
            raise GstInputError("--center must be four numbers") from e
        return x, y, max(image_w - (x + w), 0), max(image_h - (y + h), 0)
    raise GstInputError("need --insets L,T,R,B or --center X,Y,W,H")


def write_tres(path, tex_res, l, t, r, b, region=None):
    lines = [
        "[gd_resource type=\"StyleBoxTexture\" format=3]",
        "",
        '[ext_resource type="Texture2D" path="%s" id="1_tex"]' % tex_res,
        "",
        "[resource]",
        'texture = ExtResource("1_tex")',
        "texture_margin_left = %s" % float(l),
        "texture_margin_top = %s" % float(t),
        "texture_margin_right = %s" % float(r),
        "texture_margin_bottom = %s" % float(b),
    ]
    if region is not None:
        x, y, w, h = region
        lines.append("region_rect = Rect2(%s, %s, %s, %s)" % (float(x), float(y), float(w), float(h)))
    lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 StyleBoxTexture .tres from an image and insets.")
    ap.add_argument("image")
    ap.add_argument("-o", "--out", required=True, help="output .tres")
    ap.add_argument("--insets", help="L,T,R,B in pixels")
    ap.add_argument("--center", help="X,Y,W,H of the stretchable middle")
    ap.add_argument("--res", default="res://", help="res:// path or prefix for the texture")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.image, a.out, a.in_place)
    if a.json:
        safe_out.check(a.image, a.json, a.in_place)
    im = gst_read.open_image(a.image)
    l, t, r, b = parse_insets(im.size[0], im.size[1], a.insets, a.center)
    if min(l, t, r, b) < 0:
        raise GstInputError("insets must be >= 0")
    if l + r > im.size[0] or t + b > im.size[1]:
        raise GstInputError("insets exceed the image size")
    if a.res.startswith("res://") and a.res.lower().endswith((".png", ".webp", ".jpg", ".jpeg", ".svg")):
        tex = a.res
    else:
        tex = godot_text.res_path(a.res, os.path.basename(a.image))
    write_tres(a.out, tex, l, t, r, b)
    rec = {"out": a.out, "texture": tex, "insets": [l, t, r, b], "width": im.size[0], "height": im.size[1]}
    print("StyleBoxTexture insets %s -> %s" % ([l, t, r, b], a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
