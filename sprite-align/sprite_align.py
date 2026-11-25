#!/usr/bin/env python3
"""sprite-align: place a folder of sprites onto one shared canvas so a common
anchor (feet, center, centroid, or a compass point) of each sprite's opaque
content lines up. Loose images are rewritten. When an atlas JSON is given,
sourceSize and spriteSourceSize are rewritten and packed sheet pixels stay put;
a size that would clip packed content is refused, as are rotated packed frames.
The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-canvas"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
import safe_out, sprite_canvas, sprite_rotate, atlas_json  # noqa: E402


def content_box(im):
    im = im.convert("RGBA")
    a = im.getchannel("A")
    bbox = a.getbbox()
    if bbox is None:
        return (0, 0, im.size[0], im.size[1])
    return bbox


def anchor_of_box(box, anchor):
    l, t, r, b = box
    w, h = r - l, b - t
    x, y = sprite_canvas.anchor_xy(w, h, 0, 0, anchor)
    # anchor_xy(cw,ch,w,h) with w=h=0 gives the anchor point in the box
    return l + x, t + y


def union_canvas(boxes, anchors, pad=0):
    """boxes and matching anchor points (ax, ay) in each image's coords.
    Place each so its anchor sits at the origin, then shift to 0,0."""
    placed = []
    for (l, t, r, b), (ax, ay) in zip(boxes, anchors):
        placed.append((l - ax, t - ay, r - ax, b - ay))
    minx = min(p[0] for p in placed) - pad
    miny = min(p[1] for p in placed) - pad
    maxx = max(p[2] for p in placed) + pad
    maxy = max(p[3] for p in placed) + pad
    cw, ch = max(1, int(maxx - minx)), max(1, int(maxy - miny))
    # origin (anchor) in canvas coords
    ox, oy = int(-minx), int(-miny)
    return cw, ch, ox, oy


def parse_bg(s):
    return sprite_canvas.parse_color(s)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Align sprites on a shared canvas by a content anchor.")
    ap.add_argument("inputs", nargs="+", help="image files, a folder, and/or an atlas JSON")
    ap.add_argument("-o", "--out", required=True, help="output folder, or atlas JSON when aligning an atlas")
    ap.add_argument("--anchor", default="feet")
    ap.add_argument("--pad", type=int, default=0, help="extra transparent margin around the union")
    ap.add_argument("--bg", default=None)
    ap.add_argument("--atlas", help="atlas JSON (if not passed as an input)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    bg = parse_bg(a.bg)
    if a.pad < 0:
        raise SystemExit("--pad must be >= 0")

    inputs = list(a.inputs)
    atlas_path = a.atlas
    images = []
    for p in inputs:
        if os.path.isfile(p) and p.lower().endswith(".json") and atlas_path is None:
            atlas_path = p
        else:
            images.append(p)
    if atlas_path:
        safe_out.check(atlas_path, a.out, a.in_place)
        if a.json:
            safe_out.check(atlas_path, a.json, a.in_place)
        data, items, kind = atlas_json.load(atlas_path)
        if atlas_json.has_rotated(items):
            raise SystemExit("rotated packed frames are not supported")
        boxes, anchors, names = [], [], []
        for name, rec in items:
            sx, sy, sw, sh = atlas_json.sprite_source(rec)
            # treat packed content box as the opaque content in source space
            box = (sx, sy, sx + sw, sy + sh)
            boxes.append(box)
            anchors.append(anchor_of_box(box, a.anchor))
            names.append(name)
        cw, ch, ox, oy = union_canvas(boxes, anchors, a.pad)
        new_items = []
        for (name, rec), box, (ax, ay) in zip(items, boxes, anchors):
            sx, sy, sw, sh = box[0], box[1], box[2] - box[0], box[3] - box[1]
            nx, ny = ox + (ax - sx) * 0 + (sx - ax), oy + (sy - ay)
            nx, ny = ox + sx - ax, oy + sy - ay
            if nx < 0 or ny < 0 or nx + sw > cw or ny + sh > ch:
                raise SystemExit(f"{name}: aligned content would clip on a {cw}x{ch} canvas")
            rec = dict(rec)
            rec["sourceSize"] = {"w": cw, "h": ch}
            rec["spriteSourceSize"] = {"x": int(nx), "y": int(ny), "w": int(sw), "h": int(sh)}
            rec["trimmed"] = not (nx == 0 and ny == 0 and sw == cw and sh == ch)
            new_items.append((name, rec))
        meta = data.get("meta") or {}
        size = (meta.get("size") or {}).get("w") or 1, (meta.get("size") or {}).get("h") or 1
        data, new_items, _w, _h = atlas_json._store(data, new_items, size[0], size[1])
        atlas_json.save(a.out, data)
        rec = {"out": a.out, "count": len(new_items), "canvas": [cw, ch], "anchor": a.anchor}
        if a.json:
            json.dump(rec, open(a.json, "w"), indent=2)
        print("aligned %d atlas frame(s) to %dx%d -> %s" % (len(new_items), cw, ch, a.out))
        return 0

    files = [Path(p) for p in sprite_rotate.collect(images)]
    if not files:
        raise SystemExit("no images to align")
    out = Path(a.out)
    if out.exists() and out.is_file() and not a.in_place:
        # aligning images needs a folder
        pass
    for src in files:
        safe_out.check(str(src), str(out / src.name) if out.suffix.lower() not in {".png", ".webp"} else str(out), a.in_place)

    ims = []
    boxes, anchors = [], []
    for src in files:
        im = Image.open(src).convert("RGBA")
        box = content_box(im)
        boxes.append(box)
        anchors.append(anchor_of_box(box, a.anchor))
        ims.append((src, im))
    cw, ch, ox, oy = union_canvas(boxes, anchors, a.pad)
    if out.suffix.lower() in {".png", ".webp", ".gif"} and len(files) != 1:
        raise SystemExit("-o must be a folder when aligning more than one image")
    dest_dir = out if out.suffix.lower() not in {".png", ".webp", ".gif"} else out.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for (src, im), box, (ax, ay) in zip(ims, boxes, anchors):
        canvas = Image.new("RGBA", (cw, ch), bg)
        # paste image so its anchor (ax,ay) lands at (ox, oy)
        dx, dy = ox - ax, oy - ay
        canvas.alpha_composite(im, (int(dx), int(dy)))
        dest = out if (out.suffix.lower() in {".png", ".webp", ".gif"} and len(files) == 1) else dest_dir / src.name
        if dest.resolve() == src.resolve() and not a.in_place:
            raise SystemExit("refusing to overwrite the input; pick a different output path or pass --in-place")
        canvas.save(dest)
        written.append(str(dest))
    rec = {"out": str(out), "count": len(written), "canvas": [cw, ch], "anchor": a.anchor}
    if a.json:
        if a.json:
            safe_out.check(str(files[0]), a.json, a.in_place)
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("aligned %d image(s) to %dx%d -> %s" % (len(written), cw, ch, out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
