#!/usr/bin/env python3
"""sprite-recolor: remap sprite colours from a palette or a from/to list, keeping alpha.
`--map ff0000:00aaff,...` is an exact (or `--tolerance`) RGB replacement. `--from` / `--to`
are index-matched palette files (`.hex` / GIMP `.gpl`, same reader as palette-swap).
Folders or files in; writes `-o` (file or directory). Alpha is never modified. The input
is never overwritten unless `--in-place`. This is the simple remap; use palette-swap for
HSV shifts and named variants.
"""
import argparse, os, json, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "palette-swap"))
import safe_out, palette_swap  # noqa: E402


def read_palette(path):
    """Like palette-swap, but a line that is only #RRGGBB is a colour, not a comment."""
    cols = palette_swap.read_palette(path)
    if cols:
        return cols
    out = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        s = line.strip()
        if not s:
            continue
        body = s[1:] if s.startswith("#") else s
        if len(body.split()[0]) == 6 and all(c in "0123456789abcdefABCDEF" for c in body.split()[0]):
            out.append(palette_swap.hexrgb(body.split()[0]))
    return out


IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p)
                              if os.path.splitext(f)[1].lower() in IMG_EXT))
        elif os.path.splitext(p)[1].lower() in IMG_EXT:
            out.append(p)
        else:
            raise SystemExit(f"not an image or folder: {p}")
    if not out:
        raise SystemExit("no images found")
    return out


def parse_map(spec):
    mapping = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise SystemExit(f"bad --map entry {part!r} (want src:dst hex)")
        src, dst = part.split(":", 1)
        mapping.append((palette_swap.hexrgb(src), palette_swap.hexrgb(dst)))
    if not mapping:
        raise SystemExit("--map is empty")
    return mapping


def dest_of(src, out, many):
    if not many and not os.path.isdir(out) and not out.endswith(os.sep):
        return out
    os.makedirs(out, exist_ok=True)
    return os.path.join(out, os.path.basename(src))


def recolor(path, dest, mapping, tolerance):
    img = Image.open(path).convert("RGBA")
    a = np.array(img)
    rgb = a[..., :3].astype(np.int32)
    alpha = a[..., 3].copy()
    out = a.copy()
    done = np.zeros(a.shape[:2], bool)
    changed = 0
    for src, dst in mapping:
        d = np.abs(rgb - np.array(src, dtype=np.int32)).max(axis=-1)
        m = (d <= tolerance) & ~done
        n = int(m.sum())
        if n:
            out[..., :3][m] = np.array(dst, dtype=np.uint8)
            done |= m
            changed += n
    out[..., 3] = alpha
    Image.fromarray(out, "RGBA").save(dest)
    return {"file": path, "out": dest, "pixels_changed": changed}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Remap sprite colours from a palette or a from/to list, keeping alpha.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="output image (single file) or directory")
    ap.add_argument("--map", help="comma list of src:dst hex, e.g. ff0000:00aaff,00ff00:ffaa00")
    ap.add_argument("--from", dest="from_pal", help="source palette file (index-matched to --to)")
    ap.add_argument("--to", dest="to_pal", help="target palette file")
    ap.add_argument("--tolerance", type=int, default=0, help="max per-channel delta (default: 0, exact)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.tolerance < 0:
        sys.exit("--tolerance must be >= 0")
    has_map = bool(a.map)
    has_pal = bool(a.from_pal or a.to_pal)
    if has_map == has_pal or (has_pal and not (a.from_pal and a.to_pal)):
        sys.exit("pass --map, or both --from and --to")
    if a.map:
        mapping = parse_map(a.map)
    else:
        src = read_palette(a.from_pal)
        dst = read_palette(a.to_pal)
        if len(src) != len(dst):
            sys.exit(f"--from has {len(src)} colour(s) and --to has {len(dst)}")
        if not src:
            sys.exit("palette files are empty")
        mapping = list(zip(src, dst))
    paths = collect(a.inputs)
    many = len(paths) > 1 or any(os.path.isdir(p) for p in a.inputs)
    if many and os.path.splitext(a.out)[1].lower() in IMG_EXT and not os.path.isdir(a.out):
        sys.exit("-o as an image path is only valid for a single file input; pass a directory")
    recs = []
    for p in paths:
        dest = dest_of(p, a.out, many)
        os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
        safe_out.check(p, dest, a.in_place)
        if a.json:
            safe_out.check(p, a.json, a.in_place)
        recs.append(recolor(p, dest, mapping, a.tolerance))
    if a.json:
        json.dump({"files": recs, "colours": len(mapping)}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} image(s), {len(mapping)} colour pair(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
