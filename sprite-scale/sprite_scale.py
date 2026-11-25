#!/usr/bin/env python3
"""sprite-scale: nearest-neighbour scale of sprites by a uniform `--scale` factor
or to an explicit `--size WxH`. When an atlas JSON is given (`--atlas` or a
`.json` input), the packed sheet and every frame rect / sourceSize are rewritten
(`--scale`, or `--size` as the new sheet size). Folders or files in; writes `-o`
(file or directory). Alpha is kept. The input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
import safe_out, atlas_json, sprite_rotate  # noqa: E402


def parse_size(s):
    raw = s.lower().replace(",", "x")
    if "x" not in raw:
        raise SystemExit("--size must be WxH, e.g. 32x32")
    w, h = raw.split("x", 1)
    w, h = int(w), int(h)
    if w < 1 or h < 1:
        raise SystemExit("--size values must be >= 1")
    return w, h


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    return os.path.join(outdir, f"{stem}{suffix}{ext}")


def process_atlas(atlas_path, dest_image, dest_atlas, scale, size, in_place):
    data, items, _kind = atlas_json.load(atlas_path)
    src_img = atlas_json.image_path(atlas_path, data, None)
    if not os.path.isfile(src_img):
        raise SystemExit(f"atlas image not found: {src_img}")
    safe_out.check(src_img, dest_image, in_place)
    safe_out.check(atlas_path, dest_atlas, in_place)
    im = Image.open(src_img).convert("RGBA")
    if size:
        tw, th = parse_size(size)
        sx = tw / im.size[0]
        sy = th / im.size[1]
    else:
        sx = sy = scale
        tw = max(1, int(round(im.size[0] * sx)))
        th = max(1, int(round(im.size[1] * sy)))
    out = im.resize((tw, th), Image.Resampling.NEAREST)
    # use the actual resized-image ratios so meta.size matches the written sheet
    data2, _items, nw, nh = atlas_json.rewrite_scale(data, items, tw / im.size[0], th / im.size[1],
                                                     im.size[0], im.size[1])
    meta = dict(data2.get("meta") or {})
    meta["image"] = os.path.basename(dest_image)
    meta["size"] = {"w": out.size[0], "h": out.size[1]}
    data2["meta"] = meta
    os.makedirs(os.path.dirname(os.path.abspath(dest_image)) or ".", exist_ok=True)
    out.save(dest_image)
    atlas_json.save(dest_atlas, data2)
    return {"atlas": atlas_path, "image": src_img, "out_image": dest_image, "out_atlas": dest_atlas,
            "in_size": list(im.size), "out_size": list(out.size), "frames": len(items)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Nearest-neighbour scale of sprites. Rewrites an atlas JSON when given.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="output file (single input) or directory")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scale", type=float, help="uniform scale factor (e.g. 2, 0.5)")
    g.add_argument("--size", help="target size WxH, e.g. 32x32 (sheet size when an atlas is given)")
    ap.add_argument("--atlas", help="atlas-pack / TexturePacker JSON to rewrite with the sheet")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: next to the output image, same stem)")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.scale is not None and a.scale <= 0:
        sys.exit("--scale must be > 0")
    others, atlases = sprite_rotate.split_inputs(a.inputs, a.atlas)
    paths = sprite_rotate.collect(others)
    recs, atlas_recs = [], []
    if atlases:
        if len(atlases) > 1 and a.atlas_out:
            sys.exit("--atlas-out is only valid for a single atlas")
        for apath in atlases:
            data, _items, _k = atlas_json.load(apath)
            src_img = atlas_json.image_path(apath, data, None)
            paths = [p for p in paths if os.path.abspath(p) != os.path.abspath(src_img)]
            out_is_dir = os.path.isdir(a.out) or len(atlases) > 1 or not a.out.lower().endswith(
                (".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"))
            if out_is_dir:
                os.makedirs(a.out, exist_ok=True)
                dest_image = dest_of(src_img, a.out, a.suffix, None)
            else:
                dest_image = a.out
            dest_atlas = a.atlas_out or os.path.splitext(dest_image)[0] + os.path.splitext(apath)[1]
            if a.json:
                safe_out.check(apath, a.json, a.in_place)
            atlas_recs.append(process_atlas(apath, dest_image, dest_atlas, a.scale, a.size, a.in_place))
    if paths:
        out_is_dir = (os.path.isdir(a.out) or len(paths) > 1
                      or not a.out.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff")))
        if out_is_dir:
            os.makedirs(a.out, exist_ok=True)
            out_file, outdir = None, a.out
        else:
            out_file, outdir = a.out, None
            if len(paths) > 1:
                sys.exit("-o as an image path is only valid for a single input; pass a directory")
        for p in paths:
            dest = dest_of(p, outdir or os.path.dirname(os.path.abspath(out_file)), a.suffix, out_file)
            safe_out.check(p, dest, a.in_place)
            if a.json:
                safe_out.check(p, a.json, a.in_place)
            im = Image.open(p).convert("RGBA")
            if a.size:
                tw, th = parse_size(a.size)
            else:
                tw = max(1, int(round(im.size[0] * a.scale)))
                th = max(1, int(round(im.size[1] * a.scale)))
            out = im.resize((tw, th), Image.Resampling.NEAREST)
            os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
            out.save(dest)
            recs.append({"file": p, "out": dest, "in_size": list(im.size), "out_size": list(out.size)})
    if not recs and not atlas_recs:
        raise SystemExit("no images or atlas JSON found")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "atlases": atlas_recs}, open(a.json, "w"), indent=2)
    print(f"{len(recs) + len(atlas_recs)} item(s) scaled -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
