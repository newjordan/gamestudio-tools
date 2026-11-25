#!/usr/bin/env python3
"""curve-gen: turn a few control points into a smooth path you can drop into a game: camera rails, enemy and
projectile paths, rivers, roads. Kinds: catmull (centripetal Catmull-Rom through the points; alpha 0.5 avoids
loops and cusps), bezier (one Bezier curve using the points as its control polygon), linear. 2D or 3D, optional
--closed loop. Output samples have x,y[,z], arc length, normalised distance and unit tangent; --spacing
resamples at constant distance (constant speed), --count gives N samples. Writes JSON, CSV and an SVG preview.
Input: --points "0,0;4,2;8,0" or a CSV/JSON file of coordinates.
"""
import argparse, os, csv, json, sys
import numpy as np


def parse_points(s):
    return np.array([[float(v) for v in p.split(",")] for p in s.split(";") if p.strip()], float)


def load_points(path):
    if path.endswith(".json"): return np.array(json.load(open(path)), float)
    return np.array([[float(v) for v in r] for r in csv.reader(open(path)) if r and r[0].replace(".", "", 1).replace("-", "", 1).isdigit()], float)


def catmull(P, per=24, closed=False, alpha=0.5):
    P = np.asarray(P, float)
    if closed: P = np.vstack([P[-1], P, P[0], P[1]])
    else: P = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t0 = 0.0; t1 = t0 + max(np.linalg.norm(p1 - p0), 1e-9) ** alpha; t2 = t1 + max(np.linalg.norm(p2 - p1), 1e-9) ** alpha; t3 = t2 + max(np.linalg.norm(p3 - p2), 1e-9) ** alpha
        t = np.linspace(t1, t2, per, endpoint=False)[:, None]
        A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1; A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2; A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2; B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
        out.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    pts = np.vstack(out)
    return np.vstack([pts, pts[0] if closed else P[-2]])           # close the loop, or end exactly on the last control point


def bezier(P, n=100):
    P = np.asarray(P, float); t = np.linspace(0, 1, n)[:, None]; k = len(P) - 1
    from math import comb
    return sum(comb(k, i) * (1 - t) ** (k - i) * t ** i * P[i] for i in range(k + 1))


def linear(P, closed=False):
    P = np.asarray(P, float); return np.vstack([P, P[0]]) if closed else P


def arclen(pts):
    return np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])


def resample(pts, spacing=None, count=None):
    s = arclen(pts); total = s[-1]
    if count: d = np.linspace(0, total, count)
    else:
        d = np.arange(0, total, spacing)
        if total - d[-1] > 1e-9: d = np.append(d, total)
    return np.stack([np.interp(d, s, pts[:, k]) for k in range(pts.shape[1])], 1)


def annotate(pts):
    s = arclen(pts); t = np.gradient(pts, axis=0); n = np.linalg.norm(t, axis=1, keepdims=True); t = t / np.maximum(n, 1e-12)
    return [{"i": i, "p": [round(float(v), 5) for v in pts[i]], "s": round(float(s[i]), 5), "u": round(float(s[i] / s[-1]) if s[-1] else 0.0, 5), "tangent": [round(float(v), 5) for v in t[i]]} for i in range(len(pts))]


def svg(pts, ctrl, w=600):
    xy = pts[:, :2]; lo = np.minimum(xy.min(0), ctrl[:, :2].min(0)); hi = np.maximum(xy.max(0), ctrl[:, :2].max(0)); sc = (w - 40) / max((hi - lo).max(), 1e-9)
    f = lambda p: ((p[0] - lo[0]) * sc + 20, (p[1] - lo[1]) * sc + 20)
    d = " ".join(("M" if i == 0 else "L") + "%.1f,%.1f" % f(p) for i, p in enumerate(xy))
    dots = "".join('<circle cx="%.1f" cy="%.1f" r="4" fill="#e33"/>' % f(p) for p in ctrl[:, :2])
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{w}" viewBox="0 0 {w} {w}"><rect width="100%" height="100%" fill="#fff"/><path d="{d}" fill="none" stroke="#235" stroke-width="2"/>{dots}</svg>'


def build(P, kind="catmull", closed=False, per=24, spacing=None, count=None):
    P = np.asarray(P, float)
    if len(P) < 2: raise SystemExit("need at least 2 points")
    pts = {"catmull": lambda: catmull(P, per, closed), "bezier": lambda: bezier(P, per * max(len(P) - 1, 1)), "linear": lambda: linear(P, closed)}[kind]()
    if spacing or count: pts = resample(pts, spacing, count)
    return pts


def main(argv=None):
    ap = argparse.ArgumentParser(description="Smooth path generator.")
    g = ap.add_mutually_exclusive_group(required=True); g.add_argument("--points"); g.add_argument("--points-file")
    ap.add_argument("--kind", default="catmull", choices=["catmull", "bezier", "linear"]); ap.add_argument("--closed", action="store_true")
    ap.add_argument("--per-segment", type=int, default=24); ap.add_argument("--spacing", type=float); ap.add_argument("--count", type=int)
    ap.add_argument("--json"); ap.add_argument("--csv"); ap.add_argument("--svg")
    a = ap.parse_args(argv)
    P = parse_points(a.points) if a.points else load_points(a.points_file)
    pts = build(P, a.kind, a.closed, a.per_segment, a.spacing, a.count); rows = annotate(pts)
    print(f"{len(pts)} samples, length {arclen(pts)[-1]:.3f}")
    if a.json: json.dump({"kind": a.kind, "closed": a.closed, "length": rows[-1]["s"], "samples": rows}, open(a.json, "w"), indent=1)
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["i", "x", "y"] + (["z"] if pts.shape[1] > 2 else []) + ["s", "u"]); [w.writerow([r["i"]] + r["p"] + [r["s"], r["u"]]) for r in rows]
    if a.svg: open(a.svg, "w").write(svg(pts, P))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
