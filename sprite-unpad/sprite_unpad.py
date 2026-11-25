#!/usr/bin/env python3
"""sprite-unpad: crop padding off each sprite (the inverse of sprite-pad, not
a trim-to-opaque-bbox — that is sprite-trim). `--pad N` or
`--pad LEFT,TOP,RIGHT,BOTTOM`. When an atlas JSON is given, each frame's
sourceSize and spriteSourceSize shrink so trim offsets stay correct; packed
frame rects are left alone. The crop is refused if it would clip packed
content or shrink a canvas below 1x1. The input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-pad"))
import safe_out, atlas_json, sprite_rotate, sprite_pad  # noqa: E402


def crop_image(im, left, top, right, bottom):
    im = im.convert("RGBA")
    w, h = im.size
    nw, nh = w - left - right, h - top - bottom
    if nw < 1 or nh < 1:
        raise SystemExit(f"unpad would shrink {w}x{h} below 1x1")
    return im.crop((left, top, left + nw, top + nh))


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    return os.path.join(outdir, f"{stem}{suffix}{ext}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Crop padding off each sprite (inverse of sprite-pad).")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pad", required=True, help="N or LEFT,TOP,RIGHT,BOTTOM in pixels")
    ap.add_argument("--atlas", help="optional atlas JSON; sourceSize / spriteSourceSize are rewritten")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: next to -o, same stem)")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    left, top, right, bottom = sprite_pad.parse_pad(a.pad)
    others, atlases = sprite_rotate.split_inputs(a.inputs, a.atlas)
    paths = sprite_rotate.collect(others)
    if not paths and not atlases:
        raise SystemExit("no images or atlas JSON found")
    recs, atlas_recs = [], []
    if paths:
        out_is_dir = (os.path.isdir(a.out) or len(paths) > 1
                      or not a.out.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")))
        if out_is_dir:
            os.makedirs(a.out, exist_ok=True)
            out_file, outdir = None, a.out
        else:
            out_file, outdir = a.out, None
        for p in paths:
            dest = dest_of(p, outdir or os.path.dirname(os.path.abspath(out_file)), a.suffix, out_file)
            safe_out.check(p, dest, a.in_place)
            if a.json:
                safe_out.check(p, a.json, a.in_place)
            im = Image.open(p)
            out = crop_image(im, left, top, right, bottom)
            os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
            out.save(dest)
            recs.append({"file": p, "out": dest, "in_size": list(im.size), "out_size": list(out.size)})
    for apath in atlases:
        data, items, _k = atlas_json.load(apath)
        src_img = None
        try:
            src_img = atlas_json.image_path(apath, data, None)
        except SystemExit:
            src_img = None
        dest_atlas = a.atlas_out
        if not dest_atlas:
            if os.path.isdir(a.out) or not a.out.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".json")):
                os.makedirs(a.out, exist_ok=True)
                dest_atlas = os.path.join(a.out, os.path.basename(apath))
            else:
                dest_atlas = os.path.splitext(a.out)[0] + ".json"
        safe_out.check(apath, dest_atlas, a.in_place)
        sw = sh = 1
        if src_img and os.path.isfile(src_img):
            sw, sh = Image.open(src_img).size
        data2, _items, _nw, _nh = atlas_json.rewrite_unpad(data, items, left, top, right, bottom, sw, sh)
        atlas_json.save(dest_atlas, data2)
        atlas_recs.append({"atlas": apath, "out": dest_atlas, "frames": len(items)})
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "atlases": atlas_recs, "pad": [left, top, right, bottom]},
                  open(a.json, "w"), indent=2)
    print(f"{len(recs)} image(s) unpadded, {len(atlas_recs)} atlas(es) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
