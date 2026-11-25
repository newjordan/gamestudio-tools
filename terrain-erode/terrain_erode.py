#!/usr/bin/env python3
"""terrain-erode: erode a heightmap PNG (8 or 16 bit greyscale) so noise terrain looks weathered.
thermal: material slides down slopes steeper than --talus (mass conserving, 4-neighbour).
hydraulic: grid water model: rain, downhill flow, sediment capacity from flow speed, erosion and deposition,
evaporation; all sediment is dropped at the end, so total height is conserved. Also writes a flow map.
Pure numpy and deterministic. Heights are 0..1; --wrap treats the map as tileable. CPU only.
"""
import argparse, os, sys
import numpy as np
from PIL import Image

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def load(path):
    a = np.array(Image.open(path)); a = np.array(Image.open(path).convert("L")) if a.ndim == 3 else a
    return a.astype(np.float64) / (65535.0 if a.dtype == np.uint16 else 255.0)


def save16(h, path): Image.fromarray(np.clip(h * 65535 + 0.5, 0, 65535).astype(np.uint16)).save(path)


def nb(a, dy, dx, wrap):
    """value of the neighbour at offset (dy, dx) for every cell; edge cells see themselves when not wrapping."""
    if wrap: return np.roll(a, (-dy, -dx), (0, 1))
    p = np.pad(a, 1, mode="edge"); h, w = a.shape
    return p[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]


def inflow(a, dy, dx, wrap):
    """amount sent in direction (dy, dx) arrives at the neighbour; returns what each cell receives."""
    if wrap: return np.roll(a, (dy, dx), (0, 1))
    o = np.zeros_like(a); h, w = a.shape
    o[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = a[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
    return o


def thermal(h, iterations=30, talus=0.01, rate=0.5, wrap=False):
    h = h.copy()
    for _ in range(iterations):
        ex = [np.maximum(0, h - nb(h, dy, dx, wrap) - talus) for dy, dx in DIRS]
        moved = [0.25 * rate * e for e in ex]
        h -= sum(moved)
        for m, (dy, dx) in zip(moved, DIRS): h += inflow(m, dy, dx, wrap)
    return h


def hydraulic(h, iterations=60, rain=0.01, capacity=4.0, erode=0.3, deposit=0.3, evaporate=0.05, wrap=False):
    h = h.copy(); w = np.zeros_like(h); s = np.zeros_like(h); flow = np.zeros_like(h)
    for _ in range(iterations):
        w += rain
        lvl = h + w
        diffs = [np.maximum(0, lvl - nb(lvl, dy, dx, wrap)) for dy, dx in DIRS]
        tot = sum(diffs); move = np.minimum(w, tot * 0.25)
        frac = np.divide(move, np.maximum(w, 1e-12)); share = [np.divide(d, np.maximum(tot, 1e-12)) for d in diffs]
        cap = capacity * move                                                       # faster flow carries more
        e = np.where(s < cap, np.minimum((cap - s) * erode, h), 0.0); d = np.where(s > cap, (s - cap) * deposit, 0.0)
        h += d - e; s += e - d; flow += move
        out_w, out_s = [move * sh for sh in share], [s * frac * sh for sh in share]
        w -= move; s -= s * frac
        for ow, os_, (dy, dx) in zip(out_w, out_s, DIRS): w += inflow(ow, dy, dx, wrap); s += inflow(os_, dy, dx, wrap)
        w *= 1 - evaporate
    h += s                                                                           # drop what is still carried
    return h, flow / max(flow.max(), 1e-12)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Erode a heightmap.")
    ap.add_argument("height"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--flow", help="write the flow map PNG")
    ap.add_argument("--thermal", type=int, default=0, help="thermal iterations"); ap.add_argument("--talus", type=float, default=0.01)
    ap.add_argument("--hydraulic", type=int, default=0, help="hydraulic iterations"); ap.add_argument("--rain", type=float, default=0.01)
    ap.add_argument("--wrap", action="store_true")
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
    _src_keys = ('height',)
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

    h = load(a.height); flow = None
    if a.hydraulic: h, flow = hydraulic(h, a.hydraulic, a.rain, wrap=a.wrap)
    if a.thermal: h = thermal(h, a.thermal, a.talus, wrap=a.wrap)
    save16(h, a.out)
    if a.flow and flow is not None: Image.fromarray((flow ** 0.5 * 255).astype(np.uint8)).save(a.flow)
    print(f"{a.height} -> {a.out} (thermal {a.thermal}, hydraulic {a.hydraulic}), range {h.min():.3f}..{h.max():.3f}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
