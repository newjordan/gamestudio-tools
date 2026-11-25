#!/usr/bin/env python3
"""terrain-noise: seeded fBm heightmaps + biome splat maps for Godot Terrain3D / Unity / Unreal.

Own vectorised gradient-noise (Perlin-style) implementation in numpy. Outputs 8-bit PNG,
16-bit PNG, raw little-endian uint16 (.r16, Unity/Unreal), and a 4-channel biome splatmap.
"""
import argparse, os
import numpy as np
from PIL import Image
import os, sys


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(shape, period, rng, tile=True):
    h, w = shape
    gy, gx = period, period
    ang = rng.uniform(0, 2 * np.pi, (gy + 1, gx + 1))
    grads = np.stack([np.cos(ang), np.sin(ang)], -1)
    if tile:
        grads[-1, :] = grads[0, :]
        grads[:, -1] = grads[:, 0]
    ys = np.linspace(0, gy, h, endpoint=False)
    xs = np.linspace(0, gx, w, endpoint=False)
    Y, X = np.meshgrid(ys, xs, indexing="ij")
    y0, x0 = Y.astype(int), X.astype(int)
    fy, fx = Y - y0, X - x0

    def dot(iy, ix, oy, ox):
        g = grads[iy, ix]
        return g[..., 0] * ox + g[..., 1] * oy

    n00 = dot(y0, x0, fy, fx)
    n10 = dot(y0, x0 + 1, fy, fx - 1)
    n01 = dot(y0 + 1, x0, fy - 1, fx)
    n11 = dot(y0 + 1, x0 + 1, fy - 1, fx - 1)
    u, v = _fade(fx), _fade(fy)
    return (n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v


def fbm(size, seed=0, octaves=6, base_period=4, lacunarity=2, gain=0.5, ridged=False, tile=True):
    rng = np.random.default_rng(seed)
    total = np.zeros((size, size))
    amp, norm, period = 1.0, 0.0, base_period
    for _ in range(octaves):
        n = perlin((size, size), period, rng, tile)
        if ridged:
            n = 1 - np.abs(n) * 2
            n = n * n
        total += n * amp
        norm += amp
        amp *= gain
        period = int(period * lacunarity)
    total /= norm
    return (total - total.min()) / (np.ptp(total) or 1)


def island_mask(h, falloff=2.5):
    n = h.shape[0]
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    d = np.sqrt(x * x + y * y)
    return np.clip(h * (1 - np.clip(d, 0, 1) ** falloff), 0, 1)


def splat(h, water=0.3, sand=0.36, grass=0.65):
    """RGBA weights: R=sand/shore, G=grass, B=rock, A=snow; water left at 0."""
    out = np.zeros(h.shape + (4,))
    out[..., 0] = (h >= water) & (h < sand)
    out[..., 1] = (h >= sand) & (h < grass)
    out[..., 2] = (h >= grass) & (h < 0.85)
    out[..., 3] = h >= 0.85
    return (out * 255).astype(np.uint8)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate tileable/island heightmaps and splatmaps.")
    ap.add_argument("-o", "--out", default="terrain")
    ap.add_argument("--size", type=int, default=513, help="side in px (Unity likes 2^n+1)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--octaves", type=int, default=6)
    ap.add_argument("--period", type=int, default=4, help="base feature count across the map")
    ap.add_argument("--ridged", action="store_true", help="mountain ridges")
    ap.add_argument("--island", action="store_true", help="radial falloff to sea")
    ap.add_argument("--no-tile", action="store_true")
    a = ap.parse_args(argv)
    h = fbm(a.size, a.seed, a.octaves, a.period, ridged=a.ridged, tile=not a.no_tile)
    if a.island:
        h = island_mask(h)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    Image.fromarray((h * 255).astype(np.uint8), "L").save(a.out + "_8.png")
    h16 = (h * 65535).astype(np.uint16)
    Image.fromarray(h16).save(a.out + "_16.png")
    h16.astype("<u2").tofile(a.out + ".r16")
    Image.fromarray(splat(h), "RGBA").save(a.out + "_splat.png")
    print(f"wrote {a.out}_8.png, _16.png, .r16, _splat.png ({a.size}x{a.size}, seed {a.seed})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
