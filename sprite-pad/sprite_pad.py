#!/usr/bin/env python3
"""sprite-pad: add transparent padding around each sprite (not between packed
sheet frames — that is sheet-pad). `--pad N` or `--pad LEFT,TOP,RIGHT,BOTTOM`.
When an atlas JSON is given, each frame's sourceSize and spriteSourceSize are
rewritten so trim offsets stay correct; packed frame rects are left alone.
Folders or files in; writes `-o`. The input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-rotate"))
import safe_out, atlas_json, sprite_rotate  # noqa: E402


def parse_pad(s):
    parts = [int(x) for x in s.replace("x", ",").split(",")]
    if len(parts) == 1:
        n = parts[0]
        return n, n, n, n
    if len(parts) != 4:
        raise SystemExit("--pad must be N or LEFT,TOP,RIGHT,BOTTOM")
    if any(p < 0 for p in parts):
        raise SystemExit("--pad values must be >= 0")
    return parts[0], parts[1], parts[2], parts[3]


def pad_image(im, left, top, right, bottom):
    im = im.convert("RGBA")
    w, h = im.size
    canvas = Image.new("RGBA", (w + left + right, h + top + bottom), (0, 0, 0, 0))
    canvas.paste(im, (left, top), im)
    return canvas


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    return os.path.join(outdir, f"{stem}{suffix}{ext}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add transparent padding around each sprite.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pad", required=True, help="N or LEFT,TOP,RIGHT,BOTTOM in pixels")
    ap.add_argument("--atlas", help="optional atlas JSON; sourceSize / spriteSourceSize are rewritten")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: next to -o, same stem, or <outdir>/atlas.json)")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    left, top, right, bottom = parse_pad(a.pad)
    others, atlases = sprite_rotate.split_inputs(a.inputs, a.atlas)
    paths = sprite_rotate.collect(others)
    if not paths and not atlases:
        raise SystemExit("no images or atlas JSON found")
    recs = []
    # loose images
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
            out = pad_image(im, left, top, right, bottom)
            os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
            out.save(dest)
            recs.append({"file": p, "out": dest, "in_size": list(im.size), "out_size": list(out.size)})
    atlas_recs = []
    for apath in atlases:
        data, items, _k = atlas_json.load(apath)
        # if we also padded the sheet image listed as an input, use its dest size; otherwise don't rewrite pixels
        src_img = None
        try:
            src_img = atlas_json.image_path(apath, data, None)
        except SystemExit:
            src_img = None
        dest_atlas = a.atlas_out
        if not dest_atlas:
            if os.path.isdir(a.out) or (len(paths) != 1 and not a.out.lower().endswith(
                    (".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"))):
                os.makedirs(a.out if os.path.isdir(a.out) or not a.out.lower().endswith(".json") else
                            os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
                dest_atlas = os.path.join(a.out if os.path.isdir(a.out) else a.out, os.path.basename(apath))
                if not dest_atlas.endswith(".json"):
                    dest_atlas = os.path.join(a.out, os.path.basename(apath))
            else:
                dest_atlas = os.path.splitext(a.out)[0] + ".json"
        safe_out.check(apath, dest_atlas, a.in_place)
        sw = sh = 1
        if src_img and os.path.isfile(src_img):
            from PIL import Image as _I
            im = _I.open(src_img)
            sw, sh = im.size
        data2, _items, _nw, _nh = atlas_json.rewrite_pad(data, items, left, top, right, bottom, sw, sh)
        atlas_json.save(dest_atlas, data2)
        atlas_recs.append({"atlas": apath, "out": dest_atlas, "frames": len(items)})
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "atlases": atlas_recs, "pad": [left, top, right, bottom]},
                  open(a.json, "w"), indent=2)
    print(f"{len(recs)} image(s) padded, {len(atlas_recs)} atlas(es) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
