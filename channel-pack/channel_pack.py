#!/usr/bin/env python3
"""channel-pack: pack greyscale maps into RGBA channels (ORM, Unity mask map, custom) and unpack them again.

  pack   --r ao.png --g rough.png --b metal.png [--a x.png] -o orm.png      explicit channels
  pack   --preset orm --ao a.png --roughness r.png --metallic m.png -o orm.png
  pack   --preset unity-mask --metallic m.png --ao a.png --smoothness s.png -o mask.png   (R metal, G AO, B 0, A smooth)
  unpack orm.png --preset orm -o outdir/    writes ao/roughness/metallic PNGs
Missing channels get --fill (default 255 for AO, 0 otherwise via preset). Sizes are matched to the largest input.
ORM = R ambient occlusion, G roughness, B metallic (glTF / Godot / Unreal convention).
"""
import argparse, os
import numpy as np
from PIL import Image
import os, sys

PRESETS = {
    "orm": {"r": ("ao", 255), "g": ("roughness", 255), "b": ("metallic", 0)},
    "unity-mask": {"r": ("metallic", 0), "g": ("ao", 255), "b": ("detail", 0), "a": ("smoothness", 128)},
}


def load(path):
    return np.array(Image.open(path).convert("L"))


def pack(channels, fills=None, invert=()):
    """channels: dict r/g/b/a -> 2D uint8 array or None. returns RGBA PIL image."""
    fills = fills or {}
    ref = next((v for v in channels.values() if v is not None), None)
    if ref is None:
        raise SystemExit("no input maps")
    H = max(v.shape[0] for v in channels.values() if v is not None)
    W = max(v.shape[1] for v in channels.values() if v is not None)
    out = np.zeros((H, W, 4), np.uint8)
    out[..., 3] = 255
    for i, k in enumerate("rgba"):
        v = channels.get(k)
        if v is None:
            if k in fills:
                out[..., i] = fills[k]
            continue
        if v.shape != (H, W):
            v = np.array(Image.fromarray(v).resize((W, H), Image.Resampling.BILINEAR))
        out[..., i] = 255 - v if k in invert else v
    return Image.fromarray(out, "RGBA")


def unpack(img, names):
    a = np.array(img.convert("RGBA"))
    return {names[k]: Image.fromarray(a[..., i], "L") for i, k in enumerate("rgba") if k in names}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pack/unpack texture channels.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack"); p.add_argument("-o", "--out", required=True); p.add_argument("--preset", choices=PRESETS)
    for k in "rgba": p.add_argument(f"--{k}")
    for n in ("ao", "roughness", "metallic", "smoothness", "detail"): p.add_argument(f"--{n}")
    p.add_argument("--invert", default="", help="channels to invert, e.g. g (roughness<->smoothness)")
    u = sub.add_parser("unpack"); u.add_argument("input"); u.add_argument("--preset", choices=PRESETS, default="orm"); u.add_argument("-o", "--outdir", required=True)
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
    for _k in ('r','g','b','a','ao','roughness','metallic','smoothness','detail'):
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

    if a.cmd == "pack":
        ch, fills = {}, {}
        if a.preset:
            for k, (name, fill) in PRESETS[a.preset].items():
                path = getattr(a, name, None)
                ch[k] = load(path) if path else None
                fills[k] = fill
        for k in "rgba":
            if getattr(a, k):
                ch[k] = load(getattr(a, k))
        pack(ch, fills, a.invert).save(a.out)
        print(f"wrote {a.out}")
    else:
        os.makedirs(a.outdir, exist_ok=True)
        names = {k: v[0] for k, v in PRESETS[a.preset].items()}
        base = os.path.splitext(os.path.basename(a.input))[0]
        for n, im in unpack(Image.open(a.input), names).items():
            im.save(os.path.join(a.outdir, f"{base}_{n}.png"))
        print(f"wrote {len(names)} maps to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
