#!/usr/bin/env python3
"""palette-extract: pull a palette out of one or many images and save it as .hex (Lospec), .gpl (GIMP/
Aseprite/Krita), and a swatch PNG. Exact colours when the image has few; otherwise median-cut to N.
Transparent pixels are ignored. Sort by luminance, hue, or frequency. Feed the result into pixelize
(-p palette.hex) or palette-swap (--from/--to).
"""
import argparse, os
from collections import Counter
import numpy as np
from PIL import Image
import os, sys


def collect(paths):
    cnt = Counter()
    for p in paths:
        a = np.array(Image.open(p).convert("RGBA")).reshape(-1, 4)
        a = a[a[:, 3] >= 128][:, :3]
        if len(a):
            cols, n = np.unique(a, axis=0, return_counts=True)
            for c, k in zip(map(tuple, cols.tolist()), n.tolist()):
                cnt[c] += k
    return cnt


def reduce(cnt, n):
    if len(cnt) <= n:
        return cnt
    cols = np.array(list(cnt.keys()), np.uint8)
    w = np.array(list(cnt.values()))
    img = Image.fromarray(np.repeat(cols[None, :, :], 1, 0), "RGB")  # 1 x K strip of unique colours
    q = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()[: n * 3]
    idx = np.array(q).reshape(-1)
    out = Counter()
    for i in range(len(pal) // 3):
        m = idx == i
        if m.any():
            out[tuple(pal[i * 3: i * 3 + 3])] += int(w[m].sum())
    return out


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def hue(c):
    import colorsys
    return colorsys.rgb_to_hsv(*(v / 255 for v in c))[0]


def sort_colors(cnt, how):
    items = list(cnt.items())
    if how == "luminance": items.sort(key=lambda kv: lum(kv[0]))
    elif how == "hue": items.sort(key=lambda kv: (hue(kv[0]), lum(kv[0])))
    else: items.sort(key=lambda kv: -kv[1])
    return [c for c, _ in items]


def write_hex(path, cols):
    open(path, "w").write("\n".join("%02x%02x%02x" % c for c in cols) + "\n")


def write_gpl(path, cols, name):
    lines = ["GIMP Palette", f"Name: {name}", "Columns: 8", "#"] + [f"{r:3d} {g:3d} {b:3d} {'%02x%02x%02x' % (r, g, b)}" for r, g, b in cols]
    open(path, "w").write("\n".join(lines) + "\n")


def swatch(cols, size=16, per_row=16):
    rows = -(-len(cols) // per_row)
    im = Image.new("RGB", (min(len(cols), per_row) * size, rows * size), (0, 0, 0))
    for i, c in enumerate(cols):
        im.paste(c, ((i % per_row) * size, (i // per_row) * size, (i % per_row) * size + size, (i // per_row) * size + size))
    return im


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract a palette from images.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="basename (.hex .gpl _swatch.png)")
    ap.add_argument("-n", "--colors", type=int, default=16)
    ap.add_argument("--sort", choices=["luminance", "hue", "frequency"], default="luminance")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('inputs',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    cnt = collect(a.inputs)
    if not cnt:
        raise SystemExit("no opaque pixels found")
    total = len(cnt)
    cols = sort_colors(reduce(cnt, a.colors), a.sort)
    write_hex(a.out + ".hex", cols)
    write_gpl(a.out + ".gpl", cols, os.path.basename(a.out))
    swatch(cols).save(a.out + "_swatch.png")
    print(f"{total} unique colour(s) -> {len(cols)}: " + " ".join("%02x%02x%02x" % c for c in cols))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
