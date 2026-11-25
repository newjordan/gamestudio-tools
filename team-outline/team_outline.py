#!/usr/bin/env python3
"""team-outline: team-colour variants of sprites. Three ways to say what gets recoloured (combine them):
  --edge           the outline: opaque pixels that touch transparency (or the image border) in 4 directions
  --match #rrggbb  every pixel within --tol (per-channel) of that colour, for sprites with a drawn outline colour
  --key #ff00ff    a hue-keyed team area (for example magenta cloth): pixels near the key's hue become the team colour
                   with their brightness kept relative to the key, so shading survives
Teams are NAME=#rrggbb, repeated. Writes <name>_<team>.png per sprite and team. Alpha is never changed.
"""
import argparse, os, colorsys, sys
import numpy as np
from PIL import Image


def hexc(s): s = s.lstrip("#"); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.float64)


def edge_mask(a):
    op = a[..., 3] > 0; p = np.pad(op, 1, constant_values=False)
    return op & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])


def match_mask(a, color, tol):
    return (a[..., 3] > 0) & (np.abs(a[..., :3].astype(int) - hexc(color).astype(int)).max(-1) <= tol)


def hsv(rgb):
    r, g, b = [rgb[..., i] / 255.0 for i in range(3)]; mx, mn = np.maximum.reduce([r, g, b]), np.minimum.reduce([r, g, b]); d = mx - mn
    h = np.zeros_like(mx); nz = d > 1e-9
    h = np.where(nz & (mx == r), ((g - b) / np.where(nz, d, 1)) % 6, h); h = np.where(nz & (mx == g), (b - r) / np.where(nz, d, 1) + 2, h); h = np.where(nz & (mx == b), (r - g) / np.where(nz, d, 1) + 4, h)
    return h * 60, np.where(mx > 0, d / np.maximum(mx, 1e-9), 0), mx


def key_mask(a, key, hue_tol=20.0, min_sat=0.3):
    h, s, v = hsv(a[..., :3].astype(np.float64)); kh = colorsys.rgb_to_hsv(*(hexc(key) / 255))[0] * 360
    dh = np.abs((h - kh + 180) % 360 - 180)
    return (a[..., 3] > 0) & (dh <= hue_tol) & (s >= min_sat) & (v > 0.05)


def recolor(img, team, edge=False, match=None, tol=24, key=None, hue_tol=20.0):
    a = np.array(img.convert("RGBA")); out = a.copy(); tc = hexc(team)
    if key:
        m = key_mask(a, key, hue_tol); kv = max(colorsys.rgb_to_hsv(*(hexc(key) / 255))[2], 1e-6); _, _, v = hsv(a[..., :3].astype(np.float64))
        scale = np.clip(v / kv, 0, 1.3)[..., None]; tcol = np.clip(tc[None, None] * scale, 0, 255)
        out[..., :3] = np.where(m[..., None], tcol, out[..., :3])
    m2 = np.zeros(a.shape[:2], bool)
    if edge: m2 |= edge_mask(a)
    if match: m2 |= match_mask(a, match, tol)
    out[..., :3] = np.where(m2[..., None], tc, out[..., :3]); out[..., 3] = a[..., 3]
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Team-colour sprite variants.")
    ap.add_argument("images", nargs="+"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("--team", action="append", required=True, help="NAME=#rrggbb")
    ap.add_argument("--edge", action="store_true"); ap.add_argument("--match"); ap.add_argument("--tol", type=int, default=24); ap.add_argument("--key"); ap.add_argument("--hue-tol", type=float, default=20.0)
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
    _src_keys = ('images',)
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

    if not (a.edge or a.match or a.key): ap.error("choose at least one of --edge, --match, --key")
    teams = dict(t.split("=", 1) for t in a.team); os.makedirs(a.outdir, exist_ok=True); n = 0
    for p in a.images:
        base = os.path.splitext(os.path.basename(p))[0]; img = Image.open(p)
        for name, col in teams.items(): recolor(img, col, a.edge, a.match, a.tol, a.key, a.hue_tol).save(os.path.join(a.outdir, f"{base}_{name}.png")); n += 1
    print(f"{n} variant(s) -> {a.outdir}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
