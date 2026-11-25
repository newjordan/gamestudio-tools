#!/usr/bin/env python3
"""sprite-reframe: place each sprite onto a new source canvas of --size WxH
with an anchor (the same anchors as sprite-canvas). Loose images are rewritten.
When an atlas JSON is given, sourceSize and spriteSourceSize are rewritten and
the packed sheet pixels stay put; a size that would clip packed content is
refused. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-canvas"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
import safe_out, sprite_canvas, sprite_rotate, atlas_json  # noqa: E402


def parse_size(s):
    parts = s.lower().replace(" ", "").split("x")
    if len(parts) != 2:
        raise SystemExit("--size expects WxH (e.g. 16x16)")
    w, h = int(parts[0]), int(parts[1])
    if w < 1 or h < 1:
        raise SystemExit("--size must be positive")
    return w, h


def parse_bg(s):
    if not s:
        return (0, 0, 0, 0)
    h = s[1:] if s.startswith("#") else s
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (r, g, b, 255)
    if len(h) == 8:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    raise SystemExit("--bg expects #RRGGBB or #RRGGBBAA")


def reframe_atlas(data, items, cw, ch, anchor):
    """Rewrite sourceSize / spriteSourceSize; packed rects unchanged."""
    for name, rec in items:
        sw, sh = atlas_json.source_size(rec)
        sx, sy, ssw, ssh = atlas_json.sprite_source(rec)
        # the packed content occupies ssw x ssh at (sx, sy) in the old source
        # place that (ssw, ssh) box onto the new canvas
        nx, ny = sprite_canvas.anchor_xy(cw, ch, ssw, ssh, anchor)
        if nx < 0 or ny < 0 or nx + ssw > cw or ny + ssh > ch:
            raise SystemExit(
                f"{name}: packed content {ssw}x{ssh} does not fit a {cw}x{ch} source "
                f"at anchor {anchor}"
            )
        rec["sourceSize"] = {"w": cw, "h": ch}
        rec["spriteSourceSize"] = {"x": nx, "y": ny, "w": ssw, "h": ssh}
        rec["trimmed"] = not (nx == 0 and ny == 0 and ssw == cw and ssh == ch)
    # sheet size unchanged
    meta = data.get("meta") or {}
    size = (meta.get("size") or {}).get("w"), (meta.get("size") or {}).get("h")
    data, items, _w, _h = atlas_json._store(data, items, size[0] or 1, size[1] or 1)
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Place sprites on a new source canvas (WxH) with an anchor.")
    ap.add_argument("inputs", nargs="+", help="image files, a folder, and/or an atlas JSON")
    ap.add_argument("-o", "--out", required=True, help="output file or folder")
    ap.add_argument("--size", required=True, help="new source canvas WxH")
    ap.add_argument("--anchor", default="center")
    ap.add_argument("--bg", default=None)
    ap.add_argument("--atlas", help="atlas JSON (if not passed as an input)")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: next to -o)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    cw, ch = parse_size(a.size)
    bg = parse_bg(a.bg)
    # classify inputs
    images, atlas_in = [], a.atlas
    for raw in a.inputs:
        p = Path(raw)
        if p.is_file() and p.suffix.lower() == ".json" and atlas_in is None:
            atlas_in = str(p)
        else:
            images.append(str(p))
    sources = list(a.inputs) + ([atlas_in] if atlas_in else [])
    safe_out.check_any(sources, a.out, a.in_place)
    if a.atlas_out:
        safe_out.check_any(sources, a.atlas_out, a.in_place)
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)

    written = []
    out = Path(a.out)
    if images:
        files = [Path(p) for p in sprite_rotate.collect(images)]
        if out.suffix.lower() in {".png", ".gif", ".webp", ".bmp", ".jpg", ".jpeg"}:
            if len(files) != 1:
                raise SystemExit("-o as a file needs exactly one input image")
            out.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(files[0])
            sprite_canvas.place(im, cw, ch, a.anchor, bg, False, False).save(out)
            written.append(str(out))
        else:
            out.mkdir(parents=True, exist_ok=True)
            for src in files:
                dest = out / src.name
                safe_out.check(str(src), str(dest), a.in_place)
                im = Image.open(src)
                sprite_canvas.place(im, cw, ch, a.anchor, bg, False, False).save(dest)
                written.append(str(dest))

    atlas_out = None
    if atlas_in:
        data, items, _kind = atlas_json.load(atlas_in)
        if atlas_json.has_rotated(items):
            raise SystemExit("rotated packed frames are not supported")
        data = reframe_atlas(data, items, cw, ch, a.anchor)
        atlas_out = a.atlas_out
        if not atlas_out:
            if out.suffix.lower() == ".json":
                atlas_out = str(out)
            elif out.suffix.lower() in {".png", ".gif", ".webp", ".bmp"}:
                atlas_out = str(out.with_suffix(".json"))
            else:
                atlas_out = str(Path(out) / "atlas.json")
        safe_out.check(atlas_in, atlas_out, a.in_place)
        os.makedirs(os.path.dirname(os.path.abspath(atlas_out)) or ".", exist_ok=True)
        atlas_json.save(atlas_out, data)

    rec = {"count": len(written), "size": [cw, ch], "anchor": a.anchor,
           "out": a.out, "files": written, "atlas": atlas_out}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("reframed %d image(s) to %dx%d%s" % (
        len(written), cw, ch, (" + atlas " + atlas_out) if atlas_out else ""))
    if not written and not atlas_out:
        raise SystemExit("no images or atlas to reframe")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
