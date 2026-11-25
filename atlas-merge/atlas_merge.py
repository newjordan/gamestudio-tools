#!/usr/bin/env python3
"""atlas-merge: merge two or more TexturePacker-style atlas JSON files (and
their sheets) into one packed atlas. Frames are unpacked in memory and
repacked with the same packer as atlas-pack. Colliding frame names are
refused unless `--prefix` (one prefix per input, comma-separated) or
`--prefer first`. Rotated packed frames are refused. The input is never
overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys, tempfile

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "atlas-pack"))
import safe_out, atlas_json, atlas_pack  # noqa: E402


def extract(path):
    data, items, kind = atlas_json.load(path)
    if atlas_json.has_rotated(items):
        raise SystemExit(f"{path}: rotated packed frames are not supported")
    img_path = atlas_json.image_path(path, data)
    if not os.path.isfile(img_path):
        raise SystemExit(f"{path}: sheet image not found: {img_path}")
    sheet = Image.open(img_path).convert("RGBA")
    frames = []
    for name, rec in items:
        x, y, w, h = atlas_json.frame_xywh(rec)
        crop = sheet.crop((x, y, x + w, y + h))
        ss = atlas_json.source_size(rec)
        sss = atlas_json.sprite_source(rec)
        # restore onto sourceSize canvas so trim is preserved on repack
        src = Image.new("RGBA", ss, (0, 0, 0, 0))
        src.alpha_composite(crop, (sss[0], sss[1]))
        frames.append((name, src, rec))
    return frames


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Merge atlas JSON files into one packed atlas.")
    ap.add_argument("inputs", nargs="+", help="two or more atlas JSON files")
    ap.add_argument("-o", "--out", required=True, help="output basename (writes .png and .json)")
    ap.add_argument("--prefix", help="comma-separated name prefixes, one per input")
    ap.add_argument("--prefer", choices=("first", "fail"), default="fail",
                    help="on colliding names: keep the first, or refuse (default: fail)")
    ap.add_argument("--padding", type=int, default=2)
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--no-pot", action="store_true")
    ap.add_argument("--max", type=int, default=4096)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if len(a.inputs) < 2:
        raise SystemExit("atlas-merge needs at least two atlas JSON inputs")
    json_out = a.out if a.out.lower().endswith(".json") else a.out + ".json"
    png_out = json_out[:-5] + ".png" if json_out.lower().endswith(".json") else a.out + ".png"
    for src in a.inputs:
        safe_out.check(src, json_out, a.in_place)
        safe_out.check(src, png_out, a.in_place)
    if a.json:
        for src in a.inputs:
            safe_out.check(src, a.json, a.in_place)

    prefixes = [p.strip() for p in a.prefix.split(",")] if a.prefix else [""] * len(a.inputs)
    if len(prefixes) != len(a.inputs):
        raise SystemExit("--prefix needs one comma-separated prefix per input")

    merged = []  # (name, image)
    collisions = []
    seen = {}
    for src, prefix in zip(a.inputs, prefixes):
        for name, im, rec in extract(src):
            dest = f"{prefix}{name}"
            if dest in seen:
                collisions.append(dest)
                if a.prefer == "fail":
                    raise SystemExit(f"colliding frame name {dest!r} (from {src} and earlier input)")
                continue  # prefer first
            seen[dest] = src
            merged.append((dest, im))

    tmp = tempfile.TemporaryDirectory()
    paths = []
    for name, im in merged:
        # keep names with slashes flattened
        safe = name.replace("/", "_").replace("\\", "_")
        p = os.path.join(tmp.name, safe + ".png")
        # if two different names flatten to the same file, use a unique suffix
        n = 1
        while p in paths:
            p = os.path.join(tmp.name, f"{safe}_{n}.png")
            n += 1
        im.save(p)
        # atlas_pack.pack uses basename without suffix as the frame name;
        # write under the real dest name when it is a safe filename.
        if safe == name:
            paths.append(p)
        else:
            # re-save under a sidecar mapping: we will rename after pack
            paths.append(p)
    # map packed basename -> dest name
    name_for = {os.path.splitext(os.path.basename(p))[0]: dest
                for (dest, _im), p in zip(merged, paths)}

    atlas, frames = atlas_pack.pack(paths, max_size=a.max, padding=a.padding,
                                    do_trim=not a.no_trim, pot=not a.no_pot)
    remapped = {}
    for fname, rec in frames.items():
        remapped[name_for.get(fname, fname)] = rec
    os.makedirs(os.path.dirname(os.path.abspath(png_out)) or ".", exist_ok=True)
    atlas.save(png_out)
    meta = {"image": os.path.basename(png_out), "size": {"w": atlas.size[0], "h": atlas.size[1]},
            "format": "RGBA8888", "scale": "1"}
    data = {"frames": remapped, "meta": meta}
    atlas_json.save(json_out, data)
    rec = {"out": json_out, "image": png_out, "count": len(remapped),
           "inputs": list(a.inputs), "collisions": collisions,
           "size": {"w": atlas.size[0], "h": atlas.size[1]}}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    tmp.cleanup()
    print("merged %d frame(s) from %d atlas(es) -> %s" % (len(remapped), len(a.inputs), json_out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
