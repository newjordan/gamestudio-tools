#!/usr/bin/env python3
"""tile-extrude: rebuild a tileset so tiles never bleed at the edges when scaled or filtered.

--extrude N   repeat each tile's edge pixels N px outward (margin N, spacing 2N in the output).
--bleed K     fill the RGB of fully transparent pixels from nearby opaque pixels (K passes), so
              bilinear filtering and mipmaps do not pull in dark/black fringes. Alpha is unchanged.
Prints the tileset parameters (tile size, margin, spacing, columns) to plug into Tiled / Godot / Unity.
"""
import os
import argparse, json
import numpy as np
from PIL import Image
import sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402

def bleed(rgba, passes=4):
    a = np.array(rgba, dtype=np.float32)
    known = a[..., 3] > 0
    for _ in range(passes):
        if known.all():
            break
        k = known.astype(np.float32)[..., None]
        pad = lambda arr: np.pad(arr, ((1, 1), (1, 1), (0, 0)))
        rgb = a[..., :3] * k
        s = np.zeros_like(rgb)
        c = np.zeros_like(k)
        for dy, dx in ((0, 1), (2, 1), (1, 0), (1, 2)):
            s += pad(rgb)[dy:dy + a.shape[0], dx:dx + a.shape[1]]
            c += pad(k)[dy:dy + a.shape[0], dx:dx + a.shape[1]]
        fill = (~known) & (c[..., 0] > 0)
        a[fill, :3] = s[fill] / c[fill]
        known = known | fill
    return Image.fromarray(a.round().astype(np.uint8), "RGBA")


def extrude(img, tw, th, n=1, margin=0, spacing=0, bleed_passes=0):
    img = img.convert("RGBA")
    if tw < 1 or th < 1:
        raise GstInputError("tile size must be at least 1x1")
    if img.width < 1 or img.height < 1:
        raise GstInputError("tileset image is empty")
    span_w, span_h = tw + spacing, th + spacing
    if span_w < 1 or span_h < 1:
        raise GstInputError("tile size plus spacing must be at least 1")
    cols = (img.width - margin + spacing) // span_w
    rows = (img.height - margin + spacing) // span_h
    if cols < 1 or rows < 1:
        raise GstInputError("tileset is smaller than the tile size")
    # layout: margin n, each tile cell tw, spacing 2n  ->  n + cols*tw + (cols-1)*2n + n
    out_w = 2 * n + cols * tw + (cols - 1) * 2 * n
    out_h = 2 * n + rows * th + (rows - 1) * 2 * n
    if out_w < 1 or out_h < 1:
        raise GstInputError("extruded tileset would be empty")
    out = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            x = margin + c * (tw + spacing)
            y = margin + r * (th + spacing)
            tile = np.array(img.crop((x, y, x + tw, y + th)))
            if n:
                tile = np.pad(tile, ((n, n), (n, n), (0, 0)), mode="edge")
            ox = c * (tw + 2 * n)
            oy = r * (th + 2 * n)
            out.paste(Image.fromarray(tile, "RGBA"), (ox, oy))
    if bleed_passes:
        out = bleed(out, bleed_passes)
    return out, {"tilewidth": tw, "tileheight": th, "margin": n, "spacing": 2 * n, "columns": cols, "rows": rows,
                 "imagewidth": out_w, "imageheight": out_h}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extrude tile edges and bleed colour into transparent pixels.")
    ap.add_argument("tileset")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--tile", required=True, help="tile size WxH, e.g. 16x16")
    ap.add_argument("--margin", type=int, default=0, help="margin in the source tileset")
    ap.add_argument("--spacing", type=int, default=0, help="spacing in the source tileset")
    ap.add_argument("--extrude", type=int, default=1)
    ap.add_argument("--bleed", type=int, default=0, metavar="PASSES")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if getattr(a, 'out', None) and os.path.abspath(a.out) == os.path.abspath(a.tileset) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    parts = a.tile.lower().split("x")
    if len(parts) != 2:
        raise GstInputError("--tile needs WxH (for example 8x8)")
    try:
        tw, th = (int(v) for v in parts)
    except ValueError as e:
        raise GstInputError("--tile needs WxH (for example 8x8)") from e
    out, meta = extrude(Image.open(a.tileset), tw, th, a.extrude, a.margin, a.spacing, a.bleed)
    out.save(a.out)
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
