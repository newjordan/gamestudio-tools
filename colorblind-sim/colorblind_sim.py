#!/usr/bin/env python3
"""colorblind-sim: preview what a screenshot, sprite or UI looks like with common colour-vision deficiencies, and check that a
palette (team colours, rarity tiers, status icons) stays distinguishable.
sim:     protanopia, deuteranopia, tritanopia (Machado, Oliveira and Fernandes 2009 matrices, applied in linear RGB, severity 0..1)
         and achromatopsia (luminance only). Writes <name>_<type>.png.
palette: every pair of colours is compared with CIE76 delta-E under normal vision and each simulation; pairs below --min-delta are flagged
         (exit 1). A delta-E under ~10 is hard to tell apart at a glance, so use shape, icon or pattern as a second cue.
These are approximations of dichromacy for design review, not a medical tool; real vision varies.
"""
import argparse, os, itertools, sys
import numpy as np
from PIL import Image

M = {"protan": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
     "deutan": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
     "tritan": np.array([[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]])}
TYPES = ["protan", "deutan", "tritan", "achroma"]
LUM = np.array([0.2126, 0.7152, 0.0722])


def to_linear(c): c = np.asarray(c, float) / 255; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def to_srgb(l): l = np.clip(l, 0, 1); return np.where(l <= 0.0031308, l * 12.92, 1.055 * l ** (1 / 2.4) - 0.055) * 255


def simulate_rgb(rgb, kind, severity=1.0):
    lin = to_linear(rgb)
    if kind == "achroma": g = (lin @ LUM)[..., None]; out = lin * (1 - severity) + np.repeat(g, 3, -1) * severity
    else: mat = np.eye(3) * (1 - severity) + M[kind] * severity; out = lin @ mat.T
    return to_srgb(out)


def simulate(img, kind, severity=1.0):
    a = np.asarray(img.convert("RGBA"), float); rgb = simulate_rgb(a[..., :3], kind, severity)
    return Image.fromarray(np.dstack([np.round(rgb), a[..., 3]]).astype(np.uint8), "RGBA")


def lab(rgb):
    l = to_linear(rgb); xyz = l @ np.array([[0.4124564, 0.2126729, 0.0193339], [0.3575761, 0.7151522, 0.1191920], [0.1804375, 0.0721750, 0.9503041]]); xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116); return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def delta_e(a, b): return float(np.linalg.norm(lab(a) - lab(b)))
def hexc(s): s = s.strip().lstrip("#"); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], float)


def palette_report(colors, severity=1.0, min_delta=10.0):
    cols = [hexc(c) for c in colors]; out = []
    for (i, a), (j, b) in itertools.combinations(enumerate(cols), 2):
        row = {"pair": (colors[i], colors[j]), "normal": round(delta_e(a, b), 1)}
        for k in TYPES: row[k] = round(delta_e(simulate_rgb(a, k, severity), simulate_rgb(b, k, severity)), 1)
        row["worst"] = min(row[k] for k in ["normal"] + TYPES); row["flag"] = row["worst"] < min_delta; out.append(row)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Colour-vision deficiency preview and palette check.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sim"); s.add_argument("images", nargs="+"); s.add_argument("-o", "--outdir", required=True); s.add_argument("--type", default="all", choices=TYPES + ["all"]); s.add_argument("--severity", type=float, default=1.0)
    p = sub.add_parser("palette"); p.add_argument("colors", help="comma list of #rrggbb"); p.add_argument("--min-delta", type=float, default=10.0); p.add_argument("--severity", type=float, default=1.0)
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
    _src_keys = ('colors', 'images')
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

    if a.cmd == "sim":
        os.makedirs(a.outdir, exist_ok=True); n = 0
        for f in a.images:
            for k in (TYPES if a.type == "all" else [a.type]): simulate(Image.open(f), k, a.severity).save(os.path.join(a.outdir, f"{os.path.splitext(os.path.basename(f))[0]}_{k}.png")); n += 1
        print(f"{n} image(s) -> {a.outdir}"); return 0
    rep = palette_report([c.strip() for c in a.colors.split(",")], a.severity, a.min_delta)
    print(f"{'pair':<22}" + "".join(f"{k:>9}" for k in ["normal"] + TYPES))
    for r in rep: print(f"{r['pair'][0]} {r['pair'][1]:<14}" + "".join(f"{r[k]:>9}" for k in ["normal"] + TYPES) + ("   TOO CLOSE" if r["flag"] else ""))
    return 1 if any(r["flag"] for r in rep) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
