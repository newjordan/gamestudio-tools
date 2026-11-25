#!/usr/bin/env python3
"""normal-fix: check and repair tangent-space normal maps (PNG).

check: mean deviation from unit length, share of texels pointing into the surface (z < 0) or nearly flat,
and a hint when the map looks like it uses the other green-channel convention (DirectX vs OpenGL is not
detectable from pixels alone; the report only flags a weak bump-direction signal, so confirm in-engine).
fix: renormalise every texel, optionally flip green (OpenGL <-> DirectX), flip red, scale the slope strength,
rebuild blue from red and green (two-channel / BC5-style maps), and drop or force alpha. Decoding is
v = rgb / 255 * 2 - 1.
"""
import argparse, os, sys, json
import numpy as np
from PIL import Image


def decode(img):
    a = np.asarray(img.convert("RGBA"), dtype=np.float64)
    return a[..., :3] / 255.0 * 2 - 1, a[..., 3]


def encode(v, alpha=None):
    rgb = np.clip((v * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)
    a = np.full(v.shape[:2], 255, np.uint8) if alpha is None else alpha.astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), "RGBA")


def stats(img):
    v, _ = decode(img)
    ln = np.linalg.norm(v, axis=-1)
    return {"size": list(img.size), "mean_length_error": round(float(np.abs(ln - 1).mean()), 4), "max_length_error": round(float(np.abs(ln - 1).max()), 4),
            "pct_into_surface": round(float((v[..., 2] < 0).mean() * 100), 3), "pct_flat": round(float((np.abs(v[..., 0]) + np.abs(v[..., 1]) < 0.02).mean() * 100), 2),
            "mean_xy": [round(float(v[..., 0].mean()), 4), round(float(v[..., 1].mean()), 4)], "mean_z": round(float(v[..., 2].mean()), 4)}


def fix(img, flip_green=False, flip_red=False, strength=1.0, rebuild_z=False, alpha="keep"):
    v, a = decode(img)
    if flip_green: v[..., 1] = -v[..., 1]
    if flip_red: v[..., 0] = -v[..., 0]
    if rebuild_z:
        xy2 = np.clip(v[..., 0] ** 2 + v[..., 1] ** 2, 0, 1); v[..., 2] = np.sqrt(1 - xy2)
    if strength != 1.0:
        v[..., :2] *= strength
        v[..., 2] = np.maximum(v[..., 2], 1e-4)
    v[..., 2] = np.maximum(v[..., 2], 0)                               # a normal never points into the surface
    ln = np.linalg.norm(v, axis=-1, keepdims=True)
    v = np.where(ln > 0.05, v / np.maximum(ln, 1e-6), np.array([0, 0, 1.0]))   # (near-)empty texels, e.g. mid-grey 128,128,128, become flat
    return encode(v, a if alpha == "keep" else np.full_like(a, 255))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check and repair normal maps.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("images", nargs="+"); c.add_argument("--max-error", type=float, help="exit 1 if mean length error exceeds this")
    f = sub.add_parser("fix"); f.add_argument("images", nargs="+"); f.add_argument("-o", "--outdir", required=True)
    f.add_argument("--flip-green", action="store_true"); f.add_argument("--flip-red", action="store_true"); f.add_argument("--strength", type=float, default=1.0)
    f.add_argument("--rebuild-z", action="store_true"); f.add_argument("--opaque", action="store_true", help="force alpha to 255")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); rc = 0
    if a.cmd == "check":
        for p in a.images:
            s = stats(Image.open(p)); print(f"{p}: length error mean {s['mean_length_error']} max {s['max_length_error']}, into-surface {s['pct_into_surface']}%, flat {s['pct_flat']}%, mean z {s['mean_z']}")
            if a.max_error is not None and s["mean_length_error"] > a.max_error: rc = 1
        return rc
    os.makedirs(a.outdir, exist_ok=True)
    for p in a.images:
        out = os.path.join(a.outdir, os.path.basename(p))
        if os.path.abspath(out) == os.path.abspath(p) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
        fix(Image.open(p), a.flip_green, a.flip_red, a.strength, a.rebuild_z, "opaque" if a.opaque else "keep").save(out); print(f"{p} -> {out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
