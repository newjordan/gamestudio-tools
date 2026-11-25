#!/usr/bin/env python3
"""image-diff: visual regression for art assets. Compare two images, or two folders (matched by relative
path), and report changed-pixel %, max/mean difference and the bounding box of the change. Writes a heatmap
(changed pixels in red over a dimmed copy of the new image) per pair and exits 1 when a threshold is hit.
"""
import argparse, os, json, sys
import numpy as np
from PIL import Image


def diff(a, b, tol=0):
    A, B = np.array(a.convert("RGBA")).astype(int), np.array(b.convert("RGBA")).astype(int)
    if A.shape != B.shape:
        return {"size_mismatch": [list(a.size), list(b.size)], "changed_pct": 100.0, "max_diff": 255, "mean_diff": 255.0, "bbox": None}, None
    d = np.abs(A - B).max(-1)
    # pixels that are fully transparent in both images never count as changed (RGB under alpha 0 is noise)
    d = np.where((A[..., 3] == 0) & (B[..., 3] == 0), 0, d)
    m = d > tol
    ys, xs = np.where(m)
    return {"changed_pct": round(100 * float(m.mean()), 4), "changed_pixels": int(m.sum()), "max_diff": int(d.max()), "mean_diff": round(float(d.mean()), 4),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if m.any() else None}, m


def heatmap(new, mask):
    base = np.array(new.convert("RGBA")).astype(np.float32)
    base[..., :3] = base[..., :3] * 0.35 + 40
    base[..., 3] = np.maximum(base[..., 3], 90)
    base[mask] = (255, 0, 0, 255)
    return Image.fromarray(base.astype(np.uint8), "RGBA")


def pairs(a, b):
    if os.path.isdir(a) and os.path.isdir(b):
        rel = lambda root: {os.path.relpath(os.path.join(dp, f), root): os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"))}
        A, B = rel(a), rel(b)
        return [(k, A.get(k), B.get(k)) for k in sorted(set(A) | set(B))]
    return [(os.path.basename(b), a, b)]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Image / folder visual diff.")
    ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("-o", "--outdir", help="write heatmaps here")
    ap.add_argument("--tol", type=int, default=0, help="ignore per-channel differences up to this value")
    ap.add_argument("--max-changed", type=float, help="fail if any image changes more than this percent")
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
    _src_keys = ('old', 'new')
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

    rep, bad = {}, False
    for rel, pa, pb in pairs(a.old, a.new):
        if pa is None or pb is None:
            rep[rel] = {"status": "added" if pa is None else "removed"}; print(f"{'ADDED  ' if pa is None else 'REMOVED'} {rel}"); bad |= a.max_changed is not None; continue
        r, m = diff(Image.open(pa), Image.open(pb), a.tol)
        rep[rel] = {"status": "changed" if r["changed_pct"] else "same", **r}
        if r["changed_pct"]:
            print(f"CHANGED {rel}: {r['changed_pct']}% pixels, max {r['max_diff']}, bbox {r['bbox']}" + (f", size {r['size_mismatch']}" if "size_mismatch" in r else ""))
            if a.outdir and m is not None:
                os.makedirs(os.path.join(a.outdir, os.path.dirname(rel)), exist_ok=True)
                heatmap(Image.open(pb), m).save(os.path.join(a.outdir, os.path.splitext(rel)[0] + "_diff.png"))
            if a.max_changed is not None and r["changed_pct"] > a.max_changed: bad = True
    same = sum(v["status"] == "same" for v in rep.values())
    print(f"{len(rep)} compared: {same} identical, {len(rep) - same} different")
    if a.json: json.dump(rep, open(a.json, "w"), indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
