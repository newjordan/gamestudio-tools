#!/usr/bin/env python3
"""atlas-unpack: extract frames from an atlas PNG + JSON back to a folder of images.
Hash or array `frames` with `frame: {x,y,w,h}` (atlas-pack / TexturePacker). `--untrim` pastes
each crop onto a `sourceSize` canvas at `spriteSourceSize`, restoring the pre-pack padding.
Rotated frames are refused. Writes new files; the atlas is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402
from PIL import Image


def frames_of(meta):
    fr = meta.get("frames")
    if isinstance(fr, dict):
        return fr
    if isinstance(fr, list):
        out = {}
        for i, it in enumerate(fr):
            name = it.get("filename") or it.get("name") or f"frame_{i}"
            out[name] = it
        return out
    raise SystemExit("atlas JSON has no frames object or array")


def filename(name):
    base = os.path.basename(str(name))
    stem, ext = os.path.splitext(base)
    return base if ext.lower() in (".png", ".webp") else stem + ".png"


def unpack_frame(atlas, rec, untrim=False):
    if rec.get("rotated"):
        raise SystemExit("rotated frames are not supported")
    fr = rec.get("frame") or {}
    try:
        x, y, w, h = int(fr["x"]), int(fr["y"]), int(fr["w"]), int(fr["h"])
    except (KeyError, TypeError, ValueError) as e:
        raise SystemExit(f"frame is missing x,y,w,h: {e}")
    crop = atlas.crop((x, y, x + w, y + h))
    if not untrim:
        return crop
    src = rec.get("sourceSize") or {}
    sw, sh = int(src.get("w") or w), int(src.get("h") or h)
    sss = rec.get("spriteSourceSize") or {"x": 0, "y": 0, "w": w, "h": h}
    canvas = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    canvas.paste(crop, (int(sss.get("x") or 0), int(sss.get("y") or 0)))
    return canvas


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract atlas frames to a folder of images.")
    ap.add_argument("json", help="atlas JSON (hash or array frames)")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--image", help="atlas PNG (default: meta.image next to the JSON)")
    ap.add_argument("--untrim", action="store_true", help="restore sourceSize canvas and trim offset")
    ap.add_argument("--prefix", default="", help="prepended to each output filename")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    meta = json.load(open(a.json, encoding="utf-8"))
    img = a.image or os.path.join(os.path.dirname(os.path.abspath(a.json)),
                                  (meta.get("meta") or {}).get("image") or "")
    if not img or not os.path.isfile(img):
        sys.exit(f"atlas image not found: {img or '(none)'}")
    safe_out.check(a.json, a.outdir, a.in_place)
    safe_out.check(img, a.outdir, a.in_place)
    frames = frames_of(meta)
    if not frames:
        sys.exit("no frames")
    atlas = Image.open(img).convert("RGBA")
    os.makedirs(a.outdir, exist_ok=True)
    written = []
    for name, rec in frames.items():
        dest = os.path.join(a.outdir, a.prefix + filename(name))
        safe_out.check(a.json, dest, a.in_place)
        safe_out.check(img, dest, a.in_place)
        unpack_frame(atlas, rec, a.untrim).save(dest)
        written.append(os.path.basename(dest))
    print(f"{len(written)} frame(s) -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
