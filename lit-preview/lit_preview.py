#!/usr/bin/env python3
"""lit-preview: see a sprite with its normal map lit, before it goes in the engine. Lambert diffuse plus optional
Blinn-Phong specular from one or more lights, on top of an ambient term. Light positions are in sprite space (x right,
y down, z toward the viewer) as `x,y,z[,color]`; `--dir` lights are directions instead of points. --orbit N renders
an N-frame GIF with the first light circling the sprite. Alpha comes from the sprite. Normals use the usual
rgb/255*2-1 decode (green up = OpenGL; pass --flip-green for DirectX maps). This is a preview, not an engine's lighting model.
"""
import os
import argparse, math, sys
import numpy as np
from PIL import Image


def decode(nm, flip_green=False):
    v = np.asarray(nm.convert("RGB"), np.float64) / 255 * 2 - 1
    if flip_green: v[..., 1] = -v[..., 1]
    v[..., 1] = -v[..., 1]                                   # image y points down; OpenGL green points up
    ln = np.linalg.norm(v, axis=-1, keepdims=True); return np.where(ln > 0.05, v / np.maximum(ln, 1e-9), [0, 0, 1.0])


def light_vec(light, shape, directional):
    h, w = shape
    if directional:
        d = np.array(light[:3], float); d = d / max(np.linalg.norm(d), 1e-9); return np.broadcast_to(d, (h, w, 3))
    y, x = np.mgrid[0:h, 0:w] + 0.5; L = np.stack([light[0] - x, light[1] - y, np.full((h, w), float(light[2]))], -1)
    return L / np.maximum(np.linalg.norm(L, axis=-1, keepdims=True), 1e-9)


def shade(sprite, normal, lights, ambient=0.2, spec=0.0, shininess=32, directional=False, flip_green=False):
    a = np.asarray(sprite.convert("RGBA"), np.float64); n = decode(normal.resize(sprite.size), flip_green); h, w = a.shape[:2]
    lit = np.full((h, w, 3), ambient); sp = np.zeros((h, w, 3)); view = np.array([0, 0, 1.0])
    for L, col in lights:
        l = light_vec(L, (h, w), directional); c = np.array(col, float) / 255
        ndl = np.clip((n * l).sum(-1), 0, 1)[..., None]; lit += ndl * c
        if spec > 0:
            hv = l + view; hv = hv / np.maximum(np.linalg.norm(hv, axis=-1, keepdims=True), 1e-9); sp += spec * np.clip((n * hv).sum(-1), 0, 1)[..., None] ** shininess * (ndl > 0) * c
    rgb = np.clip(a[..., :3] / 255 * np.clip(lit, 0, 2) + sp, 0, 1)
    return Image.fromarray(np.dstack([(rgb * 255 + 0.5).astype(np.uint8), a[..., 3].astype(np.uint8)]), "RGBA")


def parse_light(s):
    p = s.split(","); xyz = [float(v) for v in p[:3]]; col = tuple(int(p[3].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if len(p) > 3 else (255, 255, 255); return xyz, col


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preview a sprite lit by its normal map.")
    ap.add_argument("sprite"); ap.add_argument("normal"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--light", action="append", help="x,y,z[,#rrggbb]; default is above-left of the sprite")
    ap.add_argument("--dir", action="store_true", help="treat lights as directions"); ap.add_argument("--ambient", type=float, default=0.2); ap.add_argument("--spec", type=float, default=0.0); ap.add_argument("--shininess", type=float, default=32)
    ap.add_argument("--flip-green", action="store_true"); ap.add_argument("--orbit", type=int, default=0, help="N-frame GIF with the first light circling"); ap.add_argument("--bg", default=None)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); spr, nm = Image.open(a.sprite), Image.open(a.normal)
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
    _src_keys = ('sprite','normal')
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

    w, h = spr.size; lights = [parse_light(s) for s in (a.light or [f"{-w * 0.3},{-h * 0.3},{max(w, h) * 0.6}"])]
    def finish(im):
        if a.bg: s = a.bg.lstrip("#"); bg = Image.new("RGBA", im.size, tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)); bg.alpha_composite(im); return bg
        return im
    if a.orbit:
        (x, y, z), col = lights[0]; frames = []; r = math.hypot(x - w / 2, y - h / 2) if not a.dir else 1.0
        for i in range(a.orbit):
            t = 2 * math.pi * i / a.orbit; L = ([w / 2 + r * math.cos(t), h / 2 + r * math.sin(t), z] if not a.dir else [math.cos(t), math.sin(t), z], col)
            frames.append(finish(shade(spr, nm, [L] + lights[1:], a.ambient, a.spec, a.shininess, a.dir, a.flip_green)).convert("P", palette=Image.ADAPTIVE))
        frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=80, loop=0, disposal=2); print(f"{a.orbit} frame(s) -> {a.out}")
    else: finish(shade(spr, nm, lights, a.ambient, a.spec, a.shininess, a.dir, a.flip_green)).save(a.out); print(f"lit preview -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
