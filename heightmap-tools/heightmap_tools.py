#!/usr/bin/env python3
"""heightmap-tools: small edits for greyscale heightmap PNGs (8 or 16 bit; output is 16-bit): blur (gaussian,
optionally tileable), terrace (stepped plateaus with adjustable sharpness), clamp (cut and re-stretch a height band),
normalize, invert, resize (bilinear, e.g. to 513 for engines that want 2^n+1) and slope (steepness map in degrees).
Heights are 0..1. Pairs with terrain-noise, terrain-erode and terrain-mesh.
"""
import argparse, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "terrain-erode"))
import terrain_erode  # noqa: E402

load, save16 = terrain_erode.load, terrain_erode.save16


def blur(h, sigma=2.0, wrap=False):
    if sigma <= 0: return h.copy()
    r = max(1, int(3 * sigma + 0.5)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    def conv(a, axis):
        p = np.pad(a, [(r, r) if i == axis else (0, 0) for i in range(2)], mode="wrap" if wrap else "edge")
        return sum(k[i] * np.take(p, range(i, i + a.shape[axis]), axis=axis) for i in range(len(k)))
    return conv(conv(h, 0), 1)


def terrace(h, steps=6, sharp=4.0):
    t = np.clip(h, 0, 1) * steps; i = np.floor(np.minimum(t, steps - 1e-9)); f = t - i
    f2 = f if sharp <= 1e-6 else 0.5 + 0.5 * np.tanh((f - 0.5) * sharp) / np.tanh(0.5 * sharp)
    return np.clip((i + f2) / steps, 0, 1)


def clamp(h, lo=0.0, hi=1.0):
    if hi <= lo: raise SystemExit("--hi must be greater than --lo")
    return np.clip((h - lo) / (hi - lo), 0, 1)


def normalize(h):
    lo, hi = float(h.min()), float(h.max()); return (h - lo) / (hi - lo) if hi > lo else np.zeros_like(h)


def resize(h, size):
    return np.clip(np.array(Image.fromarray(h.astype(np.float32), "F").resize((size, size), Image.BILINEAR)), 0, 1).astype(np.float64)


def slope(h, height_scale=100.0, cell=1.0):
    gy, gx = np.gradient(h * height_scale, cell); return np.degrees(np.arctan(np.hypot(gx, gy)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Heightmap edits.")
    ap.add_argument("op", choices=["blur", "terrace", "clamp", "normalize", "invert", "resize", "slope", "stats"]); ap.add_argument("height")
    ap.add_argument("-o", "--out"); ap.add_argument("--sigma", type=float, default=2.0); ap.add_argument("--wrap", action="store_true")
    ap.add_argument("--steps", type=int, default=6); ap.add_argument("--sharp", type=float, default=4.0)
    ap.add_argument("--lo", type=float, default=0.0); ap.add_argument("--hi", type=float, default=1.0); ap.add_argument("--size", type=int, default=513)
    ap.add_argument("--height-scale", type=float, default=100.0, help="slope: world height of 1.0"); ap.add_argument("--cell", type=float, default=1.0, help="slope: world size of a pixel")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); h = load(a.height)
    if a.op == "stats":
        print(f"{a.height}: {h.shape[1]}x{h.shape[0]}, min {h.min():.4f} max {h.max():.4f} mean {h.mean():.4f}, steepest {slope(h).max():.1f} deg (at height scale 100)"); return 0
    if not a.out: ap.error("-o/--out is required")
    if os.path.abspath(a.out) == os.path.abspath(a.height) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if a.op == "slope": s = slope(h, a.height_scale, a.cell); Image.fromarray(np.clip(s / 90 * 255, 0, 255).astype(np.uint8)).save(a.out); print(f"slope map (0..90 deg -> 0..255) -> {a.out}, max {s.max():.1f} deg"); return 0
    out = {"blur": lambda: blur(h, a.sigma, a.wrap), "terrace": lambda: terrace(h, a.steps, a.sharp), "clamp": lambda: clamp(h, a.lo, a.hi),
           "normalize": lambda: normalize(h), "invert": lambda: 1 - h, "resize": lambda: resize(h, a.size)}[a.op]()
    save16(out, a.out); print(f"{a.op}: {a.height} -> {a.out} ({out.shape[1]}x{out.shape[0]})"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
