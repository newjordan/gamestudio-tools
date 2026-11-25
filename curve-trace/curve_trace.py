#!/usr/bin/env python3
"""curve-trace: preview a curve-gen path (JSON samples, or control points via curve-gen) as a PNG, and optionally a
GIF of a token travelling along it. Accepts a curve-gen JSON, a JSON list of points, a CSV, or --points. Draws the
polyline, sample dots, optional tangents, and an optional sprite. 2D only (z is ignored). The input is never overwritten.
"""
import argparse, os, csv, json, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "curve-gen"))
import curve_gen  # noqa: E402


def load_samples(path, points_s, kind, count, spacing, closed):
    if points_s:
        P = curve_gen.parse_points(points_s)
        pts = curve_gen.build(P, kind, closed=closed, count=count, spacing=spacing)
        return pts, P
    if not path: sys.exit("pass a curve JSON/CSV or --points")
    low = path.lower()
    if low.endswith(".csv"):
        P = curve_gen.load_points(path)
        return curve_gen.build(P, kind, closed=closed, count=count, spacing=spacing), P
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, list):
        # either raw points [[x,y],...] or a list of sample dicts
        if data and isinstance(data[0], dict):
            pts = np.array([s.get("p") or [s.get("x"), s.get("y")] for s in data], float)
            return pts, pts[[0, -1]] if len(pts) else pts
        P = np.array(data, float)
        return curve_gen.build(P, kind, closed=closed, count=count, spacing=spacing), P
    if "samples" in data:
        pts = np.array([s["p"] if "p" in s else [s["x"], s["y"]] for s in data["samples"]], float)
        return pts, pts
    sys.exit("unrecognised curve JSON (need samples or a list of points)")


def project(pts, width, height, margin):
    xy = np.asarray(pts, float)[:, :2]
    lo, hi = xy.min(0), xy.max(0)
    span = np.maximum(hi - lo, 1e-9)
    usable = np.array([width - 2 * margin, height - 2 * margin], float)
    sc = min(usable[0] / span[0], usable[1] / span[1])
    def to(p):
        q = (np.asarray(p)[:2] - lo) * sc + margin
        # invert Y so +y is up on the page
        return int(round(q[0])), int(round(height - q[1]))
    return to, sc, lo


def draw_path(img, pts, to, color, width, dots=True, tangents=False, samples=None):
    d = ImageDraw.Draw(img)
    coords = [to(p) for p in pts]
    if len(coords) >= 2:
        d.line(coords, fill=color, width=width)
    if dots:
        for x, y in coords:
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=color)
    if tangents and samples is not None:
        for s in samples:
            p = s.get("p"); t = s.get("tangent")
            if not p or not t: continue
            x, y = to(p)
            nx, ny = to(np.array(p[:2]) + np.array(t[:2]) * 0.5)
            d.line((x, y, nx, ny), fill=(200, 80, 80, 255), width=1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preview a curve-gen path as a PNG or travelling-token GIF.")
    ap.add_argument("input", nargs="?")
    ap.add_argument("-o", "--out", required=True, help="PNG path; --gif writes a sibling or given GIF")
    ap.add_argument("--points", help='control points "0,0;4,2;8,0"')
    ap.add_argument("--kind", default="catmull", choices=("catmull", "bezier", "linear"))
    ap.add_argument("--count", type=int); ap.add_argument("--spacing", type=float)
    ap.add_argument("--closed", action="store_true")
    ap.add_argument("--width", type=int, default=256); ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--margin", type=int, default=16)
    ap.add_argument("--bg", default="#111111")
    ap.add_argument("--color", default="#7ec8ff")
    ap.add_argument("--stroke", type=int, default=2)
    ap.add_argument("--sprite", help="optional token PNG stamped at a sample (and travelling in the GIF)")
    ap.add_argument("--gif"); ap.add_argument("--gif-frames", type=int, default=24)
    ap.add_argument("--duration", type=int, default=80, help="GIF frame duration ms")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.input and os.path.abspath(a.out) == os.path.abspath(a.input):
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    pts, _ctrl = load_samples(a.input, a.points, a.kind, a.count, a.spacing, a.closed)
    if len(pts) < 2: sys.exit("need at least two samples")
    def col(s):
        h = s.lstrip("#")
        if len(h) == 6: h += "ff"
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    to, sc, lo = project(pts, a.width, a.height, a.margin)
    bg, fg = col(a.bg), col(a.color)
    img = Image.new("RGBA", (a.width, a.height), bg)
    draw_path(img, pts, to, fg, a.stroke)
    sprite = Image.open(a.sprite).convert("RGBA") if a.sprite else None
    if sprite is not None:
        x, y = to(pts[0])
        img.paste(sprite, (x - sprite.width // 2, y - sprite.height // 2), sprite)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    img.save(a.out)
    print(f"{len(pts)} sample(s), {a.width}x{a.height} -> {a.out}")
    if a.gif:
        n = max(2, a.gif_frames)
        idx = [int(round(i * (len(pts) - 1) / (n - 1))) for i in range(n)]
        frames = []
        for k in idx:
            fr = Image.new("RGBA", (a.width, a.height), bg)
            draw_path(fr, pts, to, fg, a.stroke, dots=False)
            x, y = to(pts[k])
            if sprite is not None:
                fr.paste(sprite, (x - sprite.width // 2, y - sprite.height // 2), sprite)
            else:
                d = ImageDraw.Draw(fr)
                d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 220, 80, 255))
            frames.append(fr.convert("P", palette=Image.Palette.ADAPTIVE, colors=64))
        frames[0].save(a.gif, format="GIF", save_all=True, append_images=frames[1:],
                       duration=a.duration, loop=0, optimize=True)
        print(f"  {n} gif frame(s) -> {a.gif}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
