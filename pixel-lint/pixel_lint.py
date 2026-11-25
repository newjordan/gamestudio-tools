#!/usr/bin/env python3
"""pixel-lint: catch the usual pixel-art hygiene problems before sprites ship.

Checks: too many colours (--max-colors), off-palette pixels (--palette .hex/.gpl), semi-transparent pixels
(pixel art should be alpha 0 or 255), orphan pixels (an opaque pixel with no opaque 8-neighbour: usually a
stray click), near-duplicate colours (RGB distance <= --near, candidates to merge) and non-integer scaling
hints (the image looks like an upscaled sprite: every pixel repeats in kxk blocks). Exit 1 on errors.
"""
import argparse, os, glob, json, sys
import numpy as np
from PIL import Image


def read_palette(path):
    cols = set()
    for line in open(path, encoding="utf-8", errors="ignore"):
        p = line.split()
        if not p or p[0].startswith(("#", ";", "GIMP", "Name", "Columns")):
            continue
        if len(p) >= 3 and all(x.isdigit() for x in p[:3]):
            cols.add(tuple(int(x) for x in p[:3]))
        elif len(p[0].lstrip("#")) == 6:
            h = p[0].lstrip("#"); cols.add(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    return cols


def detect_scale(a):
    """largest k>1 such that the image is made of identical kxk blocks, else 1."""
    h, w = a.shape[:2]
    for k in range(min(h, w, 16), 1, -1):
        if h % k or w % k:
            continue
        blocks = a.reshape(h // k, k, w // k, k, -1)
        if (blocks == blocks[:, :1, :, :1, :]).all():
            return k
    return 1


def lint(path, max_colors=None, palette=None, near=0, allow_semi=False):
    a = np.array(Image.open(path).convert("RGBA"))
    issues = []
    alpha = a[..., 3]
    solid = alpha > 0
    if not solid.any():
        return [("warn", "image is fully transparent")]
    rgb = a[..., :3][solid]
    uniq, counts = np.unique(rgb, axis=0, return_counts=True)
    if max_colors and len(uniq) > max_colors:
        issues.append(("error", f"{len(uniq)} colours > {max_colors}"))
    if palette:
        bad = [tuple(c) for c in uniq.tolist() if tuple(c) not in palette]
        if bad:
            issues.append(("error", f"{len(bad)} off-palette colour(s), e.g. " + " ".join("%02x%02x%02x" % c for c in bad[:5])))
    if not allow_semi:
        semi = int(((alpha > 0) & (alpha < 255)).sum())
        if semi:
            issues.append(("warn", f"{semi} semi-transparent pixel(s)"))
    p = np.pad(solid, 1)
    nb = sum(p[1 + dy:1 + dy + solid.shape[0], 1 + dx:1 + dx + solid.shape[1]].astype(int)
             for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
    orphans = np.argwhere(solid & (nb == 0))
    if len(orphans):
        issues.append(("warn", f"{len(orphans)} orphan pixel(s), first at x={orphans[0][1]} y={orphans[0][0]}"))
    if near and len(uniq) > 1:
        u = uniq.astype(int)
        d = np.abs(u[:, None, :] - u[None, :, :]).max(-1)
        pairs = [(i, j) for i in range(len(u)) for j in range(i + 1, len(u)) if 0 < d[i, j] <= near]
        if pairs:
            i, j = pairs[0]
            issues.append(("warn", f"{len(pairs)} near-duplicate colour pair(s), e.g. %02x%02x%02x ~ %02x%02x%02x" % (*uniq[i], *uniq[j])))
    k = detect_scale(a)
    if k > 1:
        issues.append(("warn", f"looks upscaled {k}x (pixels repeat in {k}x{k} blocks); ship the 1x sprite and scale in-engine"))
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pixel-art hygiene linter.")
    ap.add_argument("inputs", nargs="+", help="PNG files, globs or folders")
    ap.add_argument("--max-colors", type=int)
    ap.add_argument("--palette")
    ap.add_argument("--near", type=int, default=0, help="flag colour pairs closer than this (0 = off)")
    ap.add_argument("--allow-semi", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--json")
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

    files = []
    for p in a.inputs:
        files += sorted(glob.glob(os.path.join(p, "**", "*.png"), recursive=True)) if os.path.isdir(p) else sorted(glob.glob(p)) or [p]
    pal = read_palette(a.palette) if a.palette else None
    res, err, warn = [], 0, 0
    for f in files:
        for level, msg in lint(f, a.max_colors, pal, a.near, a.allow_semi):
            res.append({"file": f, "level": level, "msg": msg}); print(f"{level.upper():5} {f}: {msg}")
            err += level == "error"; warn += level == "warn"
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    print(f"{len(files)} file(s): {err} error(s), {warn} warning(s)")
    return 1 if err or (a.strict and warn) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
