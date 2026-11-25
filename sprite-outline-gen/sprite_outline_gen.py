#!/usr/bin/env python3
"""sprite-outline-gen: add a 1px (or N-px) outline to sprites, animation frames or a grid sheet. Modes: outer (around the
opaque silhouette), inner (eaten from the edge, size unchanged) or both. 4- or 8-connected. Colour and alpha threshold are
configurable. When several frames are processed together, the SAME padding is added to every frame so animations stay aligned
(outer outlines only; inner outlines never change the canvas). --keep-size crops back to the input size (and may clip an outer
outline). A sheet with --grid WxH is sliced, outlined, and restacked with the new frame size. Distinct from sprite-fx, which only
grows an outer outline and also bakes shadows and flashes: this tool is outline-only and supports inner outlines and sheets.
"""
import argparse, os, glob, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-fx"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-slice"))
import sprite_fx, sprite_slice  # noqa: E402


def shrink(mask, n, eight=True):
    """Erode a boolean mask n times (the inverse of sprite_fx.grow)."""
    m = mask.copy()
    for _ in range(n):
        g = m.copy()
        g[1:, :] &= m[:-1, :]; g[:-1, :] &= m[1:, :]; g[:, 1:] &= m[:, :-1]; g[:, :-1] &= m[:, 1:]
        if eight:
            g[1:, 1:] &= m[:-1, :-1]; g[1:, :-1] &= m[:-1, 1:]; g[:-1, 1:] &= m[1:, :-1]; g[:-1, :-1] &= m[1:, 1:]
        m = g
    return m


def parse_color(s):
    s = s.lstrip("#")
    if len(s) == 6: return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    if len(s) == 8: return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
    raise SystemExit(f"colour {s!r} must be #rrggbb or #rrggbbaa")


def outline_one(im, width=1, mode="outer", eight=True, color=(0, 0, 0, 255), threshold=0, pad=None):
    a = np.array(im.convert("RGBA")); solid = a[..., 3] > threshold
    if mode in ("outer", "both"):
        p = width if pad is None else pad
        if p:
            a = np.pad(a, ((p, p), (p, p), (0, 0))); solid = np.pad(solid, p)
    # both rings are computed from the original silhouette so an inner ring does not eat a just-painted outer one
    outer = sprite_fx.grow(solid, width, eight) & ~solid if mode in ("outer", "both") else None
    inner = solid & ~shrink(solid, width, eight) if mode in ("inner", "both") else None
    if outer is not None: a[outer] = color
    if inner is not None: a[inner] = color
    return Image.fromarray(a, "RGBA")


def pad_needed(ims, width, mode, threshold):
    if mode == "inner": return 0
    return width


def apply(ims, width=1, mode="outer", eight=True, color=(0, 0, 0, 255), threshold=0, keep_size=False):
    ims = [i.convert("RGBA") for i in ims]; pad = 0 if keep_size else pad_needed(ims, width, mode, threshold)
    sizes = [i.size for i in ims]
    out = [outline_one(i, width, mode, eight, color, threshold, pad if not keep_size else 0) for i in ims]
    if keep_size:
        cropped = []
        for o, (w, h) in zip(out, sizes):
            if o.size == (w, h): cropped.append(o)
            else:
                L = (o.width - w) // 2; T = (o.height - h) // 2; cropped.append(o.crop((L, T, L + w, T + h)))
        out = cropped
    return out, pad


def load_inputs(paths, grid=None):
    files, ims, kind = [], [], "files"
    if grid and len(paths) == 1 and not os.path.isdir(paths[0]):
        sheet = Image.open(paths[0]).convert("RGBA"); boxes = sprite_slice.grid_slice(sheet, *grid)
        return [paths[0]] * len(boxes), [sheet.crop(b) for b in boxes], "sheet"
    for p in paths:
        batch = sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else (sorted(glob.glob(p)) or [p])
        for f in batch:
            files.append(f); ims.append(Image.open(f).convert("RGBA"))
    if not ims: raise SystemExit("no input images")
    return files, ims, kind


def restack(frames, cols, fw, fh):
    rows = -(-len(frames) // cols); s = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
    for i, f in enumerate(frames): s.paste(f, ((i % cols) * fw, (i // cols) * fh))
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add an inner or outer outline to sprites or a sheet.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--width", type=int, default=1); ap.add_argument("--mode", choices=["outer", "inner", "both"], default="outer")
    ap.add_argument("--connect", choices=["4", "8"], default="8"); ap.add_argument("--color", default="#000000")
    ap.add_argument("--threshold", type=int, default=0); ap.add_argument("--keep-size", action="store_true")
    ap.add_argument("--grid", help="frame size WxH when INPUT is a sprite sheet")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.width < 1: sys.exit("--width must be at least 1")
    grid = tuple(int(v) for v in a.grid.lower().split("x")) if a.grid else None
    files, ims, kind = load_inputs(a.inputs, grid)
    outs, pad = apply(ims, a.width, a.mode, a.connect == "8", parse_color(a.color), a.threshold, a.keep_size)
    if kind == "sheet":
        w, h = outs[0].size; cols = Image.open(a.inputs[0]).width // grid[0]; restack(outs, cols, w, h).save(a.out)
        print(f"{len(outs)} frame(s), {a.mode} {a.width}px outline, frame size {w}x{h} (padding {pad}) -> {a.out}")
        return 0
    single = len(outs) == 1 and os.path.splitext(a.out)[1].lower() == ".png"
    if not single: os.makedirs(a.out, exist_ok=True)
    for f, im in zip(files, outs):
        dest = a.out if single else os.path.join(a.out, os.path.basename(f))
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
        im.save(dest)
    print(f"{len(outs)} image(s), {a.mode} {a.width}px outline, padding {pad if not a.keep_size else 0} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
