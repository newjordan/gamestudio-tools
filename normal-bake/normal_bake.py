#!/usr/bin/env python3
"""normal-bake: derive normal, height, roughness and AO maps from a single texture.

Classic image-processing approach (luminance-as-height, Sobel gradients, blurred-difference AO).
No ML model; runs on CPU anywhere. OpenGL (Godot/Blender) or DirectX (Unreal) green channel.
"""
import argparse, os
from PIL import Image, ImageFilter
import numpy as np
import os, sys


def to_height(img, invert=False, blur=1.0):
    g = img.convert("L")
    if blur > 0:
        g = g.filter(ImageFilter.GaussianBlur(blur))
    h = np.asarray(g, dtype=np.float32) / 255.0
    return 1.0 - h if invert else h


def _grad(h, tile):
    if tile:
        dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
        dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    else:
        p = np.pad(h, 1, mode="edge")
        dx = (p[1:-1, 2:] - p[1:-1, :-2]) * 0.5
        dy = (p[2:, 1:-1] - p[:-2, 1:-1]) * 0.5
    return dx, dy


def normal_map(h, strength=4.0, directx=False, tile=True):
    dx, dy = _grad(h, tile)
    # image rows grow downward; OpenGL wants +Y up, so dh/dy_up = -dy
    nx, ny, nz = -dx * strength, dy * strength, np.ones_like(h)
    if directx:
        ny = -ny
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8), "RGB")


def ao_map(h, radius=8, strength=1.5):
    img = Image.fromarray((h * 255).astype(np.uint8))
    blur = np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0
    ao = 1.0 - np.clip((blur - h) * strength, 0, 1)
    return Image.fromarray((ao * 255).astype(np.uint8), "L")


def roughness_map(img, base=0.6, contrast=0.5):
    g = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
    r = np.clip(base + (0.5 - g) * contrast, 0, 1)
    return Image.fromarray((r * 255).astype(np.uint8), "L")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake normal/height/AO/roughness from one texture.")
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--strength", type=float, default=4.0)
    ap.add_argument("--directx", action="store_true", help="DirectX/Unreal green channel")
    ap.add_argument("--invert", action="store_true", help="dark = high")
    ap.add_argument("--no-tile", action="store_true", help="don't wrap edges (non-tileable textures)")
    ap.add_argument("--blur", type=float, default=1.0)
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
    _src_keys = ('input',)
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

    os.makedirs(a.outdir, exist_ok=True)
    src = Image.open(a.input)
    base = os.path.splitext(os.path.basename(a.input))[0]
    h = to_height(src, a.invert, a.blur)
    Image.fromarray((h * 255).astype(np.uint8), "L").save(os.path.join(a.outdir, f"{base}_height.png"))
    normal_map(h, a.strength, a.directx, not a.no_tile).save(os.path.join(a.outdir, f"{base}_normal.png"))
    ao_map(h).save(os.path.join(a.outdir, f"{base}_ao.png"))
    roughness_map(src).save(os.path.join(a.outdir, f"{base}_roughness.png"))
    print(f"wrote {base}_height/_normal/_ao/_roughness.png to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
