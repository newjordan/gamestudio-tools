#!/usr/bin/env python3
"""sprite-rotate: rotate sprites by 90/180/270 degrees exactly, or by an arbitrary
angle with nearest-neighbour sampling. 90-degree steps use a lossless transpose;
other angles expand the canvas to fit unless `--keep-size` pads/crops back to the
original size. When an atlas JSON is given (`--atlas` or a `.json` input), the
packed sheet and every frame rect / sourceSize are rewritten (90/180/270 only).
Folders or files in; writes `-o` (file or directory). Alpha is kept. The input
is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out, atlas_json  # noqa: E402

EXACT = {90: Image.Transpose.ROTATE_90, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_270}


def collect(paths):
    """Image files or folders of images. `.json` atlas paths are skipped (handled separately)."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p)
                              if f.lower().endswith((".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"))))
        elif os.path.isfile(p):
            if p.lower().endswith(".json"):
                continue
            out.append(p)
        else:
            raise SystemExit(f"not a file or folder: {p}")
    return out


def split_inputs(paths, atlas_flag):
    atlases = []
    others = []
    for p in paths:
        if os.path.isfile(p) and p.lower().endswith(".json"):
            atlases.append(p)
        else:
            others.append(p)
    if atlas_flag:
        atlases.append(atlas_flag)
    # unique, preserve order
    seen = set()
    uniq = []
    for p in atlases:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            uniq.append(p)
    return others, uniq


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    return os.path.join(outdir, f"{stem}{suffix}{ext}")


def rotate_image(im, angle, keep_size):
    im = im.convert("RGBA")
    a = angle % 360
    nearest = min(EXACT, key=lambda k: min((a - k) % 360, (k - a) % 360)) if a else 0
    dist = min((a - nearest) % 360, (nearest - a) % 360) if a else 0
    if a == 0:
        out = im
    elif dist < 1e-9 and nearest in EXACT:
        out = im.transpose(EXACT[nearest])
    else:
        out = im.rotate(-a, resample=Image.Resampling.NEAREST, expand=not keep_size, fillcolor=(0, 0, 0, 0))
    if keep_size and out.size != im.size:
        canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
        x = (im.size[0] - out.size[0]) // 2
        y = (im.size[1] - out.size[1]) // 2
        canvas.paste(out, (x, y), out)
        out = canvas
    return out


def process_atlas(atlas_path, image_override, dest_image, dest_atlas, angle, keep_size, in_place):
    data, items, _kind = atlas_json.load(atlas_path)
    src_img = atlas_json.image_path(atlas_path, data, image_override)
    if not os.path.isfile(src_img):
        raise SystemExit(f"atlas image not found: {src_img}")
    safe_out.check(src_img, dest_image, in_place)
    safe_out.check(atlas_path, dest_atlas, in_place)
    if keep_size and atlas_json.exact_angle(angle) in (90, 270):
        raise SystemExit("packed atlas rewrite cannot use --keep-size with a 90/270 rotation (the sheet swaps sides)")
    im = Image.open(src_img)
    out = rotate_image(im, angle, keep_size)
    data2, _items, nw, nh = atlas_json.rewrite_rotate(data, items, angle, im.size[0], im.size[1])
    # rewrite_rotate already used the pre-rotation sheet size; dest image must match
    if out.size != (nw, nh) and atlas_json.exact_angle(angle) is not None and not keep_size:
        raise SystemExit(f"internal size mismatch: image {out.size} vs atlas {(nw, nh)}")
    os.makedirs(os.path.dirname(os.path.abspath(dest_image)) or ".", exist_ok=True)
    out.save(dest_image)
    # if the sheet was written under a new basename, point meta.image at it
    meta = dict(data2.get("meta") or {})
    meta["image"] = os.path.basename(dest_image)
    data2["meta"] = meta
    atlas_json.save(dest_atlas, data2)
    return {"atlas": atlas_path, "image": src_img, "out_image": dest_image, "out_atlas": dest_atlas,
            "in_size": list(im.size), "out_size": list(out.size), "frames": len(items)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rotate sprites 90/180/270 or by an arbitrary angle (nearest-neighbour). Rewrites an atlas JSON when given.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="output file (single input) or directory")
    ap.add_argument("--angle", type=float, required=True, help="degrees, counter-clockwise (90/180/270 are exact)")
    ap.add_argument("--keep-size", action="store_true",
                    help="pad/crop back to the original canvas (default: expand to fit)")
    ap.add_argument("--atlas", help="atlas-pack / TexturePacker JSON to rewrite with the sheet")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: next to the output image, same stem)")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    others, atlases = split_inputs(a.inputs, a.atlas)
    paths = collect(others)
    recs = []
    atlas_recs = []

    if atlases:
        # When an atlas is given, the associated sheet is the primary output.
        # Loose images in the same invocation are still rotated independently.
        if len(atlases) > 1 and a.atlas_out:
            sys.exit("--atlas-out is only valid for a single atlas")
        for apath in atlases:
            data, _items, _k = atlas_json.load(apath)
            src_img = atlas_json.image_path(apath, data, None)
            # if the sheet was also listed as an input, don't process it twice as a loose image
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
            atlas_recs.append(process_atlas(apath, None, dest_image, dest_atlas, a.angle, a.keep_size, a.in_place))

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
            im = Image.open(p)
            out = rotate_image(im, a.angle, a.keep_size)
            os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
            out.save(dest)
            recs.append({"file": p, "out": dest, "in_size": list(im.size), "out_size": list(out.size), "angle": a.angle})

    if not recs and not atlas_recs:
        raise SystemExit("no images or atlas JSON found")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "atlases": atlas_recs, "angle": a.angle}, open(a.json, "w"), indent=2)
    n = len(recs) + len(atlas_recs)
    print(f"{n} item(s) rotated {a.angle:g} deg -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
