#!/usr/bin/env python3
"""tex-gen: procedural tileable textures for prototyping: bricks, planks, checker, cells (voronoi stone), noise.
Writes albedo PNG, plus optional height and normal maps derived from the same pattern. Every pattern tiles
seamlessly by construction (integer repeat counts, wrapped distances, periodic noise). Seeded and deterministic.
Colours are hex (#rrggbb). Meant for greybox/prototype surfaces, not final art.
"""
import argparse, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "terrain-noise"))
import terrain_noise  # noqa: E402

PATTERNS = ["bricks", "planks", "checker", "cells", "noise"]


def hexc(s): s = s.lstrip("#"); return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.float64) / 255


def bricks(size, rng, rows=8, cols=4, mortar=0.08):
    y, x = np.mgrid[0:size, 0:size] / size
    r = np.floor(y * rows).astype(int); xo = x * cols + (r % 2) * 0.5; c = np.floor(xo).astype(int) % cols
    fx, fy = xo % 1.0, (y * rows) % 1.0
    brick = (fx > mortar / 2 * cols / rows * 2) & (fx < 1 - mortar / 2 * cols / rows * 2) & (fy > mortar) & (fy < 1 - mortar)
    ids = rng.random((rows, cols)); return brick, ids[r, c], np.minimum.reduce([fx, 1 - fx, fy, 1 - fy])


def planks(size, rng, count=5, gap=0.03):
    x = np.arange(size)[None, :] / size * np.ones((size, 1)); y = np.arange(size)[:, None] / size * np.ones((1, size))
    i = np.floor(x * count).astype(int); f = (x * count) % 1.0
    grain = terrain_noise.fbm(size, seed=int(rng.integers(1 << 30)), octaves=3, base_period=2, tile=True)
    ids = rng.random(count); return (f > gap * count / 2) & (f < 1 - gap * count / 2), ids[i] * 0.6 + grain * 0.4, np.minimum(f, 1 - f)


def checker(size, rng, n=8):
    y, x = np.mgrid[0:size, 0:size] / size; m = (np.floor(x * n) + np.floor(y * n)) % 2
    return np.ones((size, size), bool), m, np.ones((size, size))


def cells(size, rng, n=10):
    pts = rng.random((n, 2)); y, x = np.mgrid[0:size, 0:size] / size
    d = []
    for p in pts:
        dx = np.abs(x - p[0]); dx = np.minimum(dx, 1 - dx); dy = np.abs(y - p[1]); dy = np.minimum(dy, 1 - dy); d.append(np.hypot(dx, dy))
    d = np.stack(d); order = np.sort(d, 0); idx = d.argmin(0)
    edge = order[1] - order[0]; return edge > 0.012, rng.random(n)[idx], np.clip(edge * 12, 0, 1)


def noise(size, rng, **_):
    n = terrain_noise.fbm(size, seed=int(rng.integers(1 << 30)), octaves=5, base_period=4, tile=True); return np.ones((size, size), bool), n, n


def normal_from_height(h, strength=1.0):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength * h.shape[1] / 16; dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength * h.shape[0] / 16
    n = np.dstack([-dx, -dy, np.ones_like(h)]); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return Image.fromarray(((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), "RGB")


def generate(pattern, size=256, seed=0, a="#a0523d", b="#6b2f20", mortar="#b8b2a6", **kw):
    rng = np.random.default_rng(seed)
    fn = {"bricks": bricks, "planks": planks, "checker": checker, "cells": cells, "noise": noise}[pattern]
    body, var, edge = fn(size, rng, **kw)
    ca, cb, cm = hexc(a), hexc(b), hexc(mortar)
    base = ca[None, None] * (1 - var[..., None]) + cb[None, None] * var[..., None]
    grain = terrain_noise.fbm(size, seed=seed + 1, octaves=4, base_period=8, tile=True)[..., None]
    col = np.where(body[..., None], base * (0.85 + 0.3 * grain), cm[None, None] * (0.9 + 0.2 * grain))
    height = np.where(body, 0.5 + 0.5 * np.clip(edge * 4, 0, 1), 0.0)
    return Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB"), height


def main(argv=None):
    ap = argparse.ArgumentParser(description="Procedural tileable textures.")
    ap.add_argument("pattern", choices=PATTERNS); ap.add_argument("-o", "--out", required=True, help="albedo PNG; _height/_normal siblings are optional")
    ap.add_argument("--size", type=int, default=256); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--color-a", default="#a0523d"); ap.add_argument("--color-b", default="#6b2f20"); ap.add_argument("--mortar-color", default="#b8b2a6")
    ap.add_argument("--count", type=int, help="bricks: rows, planks: planks, checker: squares, cells: points")
    ap.add_argument("--height", action="store_true"); ap.add_argument("--normal", action="store_true")
    a = ap.parse_args(argv)
    kw = {}
    if a.count: kw = {"bricks": {"rows": a.count, "cols": max(2, a.count // 2)}, "planks": {"count": a.count}, "checker": {"n": a.count}, "cells": {"n": a.count}, "noise": {}}[a.pattern]
    img, h = generate(a.pattern, a.size, a.seed, a.color_a, a.color_b, a.mortar_color, **kw)
    base = os.path.splitext(a.out)[0]; img.save(a.out); print(f"wrote {a.out}")
    if a.height: Image.fromarray((h * 255).astype(np.uint8)).save(base + "_height.png"); print(f"wrote {base}_height.png")
    if a.normal: normal_from_height(h).save(base + "_normal.png"); print(f"wrote {base}_normal.png")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
