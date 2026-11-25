#!/usr/bin/env python3
"""palette-swap: make recolour variants of sprites (enemy tiers, team colours, day/night).

Modes: --map "ff0000:00aaff,..." exact (or --tolerance) colour replacement; --from/--to palette files
(index-matched, .hex/.gpl); --hue DEG / --sat / --val global HSV shift; --variants variants.json writes
one output per named variant ({"blue": {"ff0000": "0000ff"}, "ghost": {"hue": 180}}). Alpha preserved.
--map also accepts a file of from:to pairs, or a JSON object of colour mappings.
"""
import argparse, sys, json, os
import numpy as np
from PIL import Image
import os, sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def hexrgb(s):
    s = (s or "").strip().lstrip("#")
    if len(s) != 6:
        raise GstInputError("palette colour must be 6 hex digits, got %r" % s)
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError as e:
        raise GstInputError("palette colour is not valid hex: %r" % s) from e


def parse_map(raw):
    """Parse a --map value: from:to pairs, or a JSON object of colour mappings."""
    text = (raw or "").strip()
    if not text:
        raise GstInputError("palette --map is empty")
    if text[:1] in "{[":
        doc = gst_read.parse_json_bytes(text, "palette map")
        if not isinstance(doc, dict):
            raise GstInputError("palette --map JSON must be an object of from:to colours")
        out = {}
        for k, v in doc.items():
            out[str(k).strip().lstrip("#")] = str(v).strip().lstrip("#")
        if not out:
            raise GstInputError("palette --map is empty")
        return out
    text = raw.replace('\n', ",").replace(" ", "")
    pairs = [p for p in text.split(",") if p]
    if not pairs:
        raise GstInputError("palette --map is empty")
    spec = {}
    for pair in pairs:
        bits = pair.split(":")
        if len(bits) != 2 or not bits[0] or not bits[1]:
            raise GstInputError("palette --map needs from:to pairs (for example ff0000:00aaff)")
        spec[bits[0].strip().lstrip("#")] = bits[1].strip().lstrip("#")
    return spec


def read_palette(path):
    cols = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith(("#", ";", "GIMP", "Name", "Columns")):
            continue
        p = line.split()
        if len(p) >= 3 and all(x.isdigit() for x in p[:3]):
            cols.append(tuple(int(x) for x in p[:3]))
        elif len(p[0].lstrip("#")) == 6:
            cols.append(hexrgb(p[0]))
    return cols


def swap_colors(img, mapping, tolerance=0):
    a = np.array(img.convert("RGBA"))
    rgb = a[..., :3].astype(np.int32)
    out = a.copy()
    done = np.zeros(a.shape[:2], bool)
    for src, dst in mapping:
        d = np.abs(rgb - np.array(src)).max(axis=-1)
        m = (d <= tolerance) & ~done
        out[m, :3] = dst
        done |= m
    return Image.fromarray(out, "RGBA")


def hsv_shift(img, hue=0, sat=1.0, val=1.0):
    a = img.convert("RGBA")
    alpha = a.getchannel("A")
    h, s, v = a.convert("RGB").convert("HSV").split()
    h = h.point(lambda x: (x + round(hue / 360 * 256)) % 256)
    s = s.point(lambda x: min(255, round(x * sat)))
    v = v.point(lambda x: min(255, round(x * val)))
    rgb = Image.merge("HSV", (h, s, v)).convert("RGB")
    rgb.putalpha(alpha)
    return rgb


def apply_variant(img, spec, tolerance=0):
    out = img
    colors = {k: v for k, v in spec.items() if k not in ("hue", "sat", "val")}
    if colors:
        out = swap_colors(out, [(hexrgb(k), hexrgb(v)) for k, v in colors.items()], tolerance)
    if any(k in spec for k in ("hue", "sat", "val")):
        out = hsv_shift(out, spec.get("hue", 0), spec.get("sat", 1.0), spec.get("val", 1.0))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recolour sprites.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--map", help="'ff0000:00aaff,00ff00:ffaa00'")
    ap.add_argument("--from", dest="src", help="palette file (source)")
    ap.add_argument("--to", dest="dst", help="palette file (target), index-matched to --from")
    ap.add_argument("--hue", type=float, default=0)
    ap.add_argument("--sat", type=float, default=1.0)
    ap.add_argument("--val", type=float, default=1.0)
    ap.add_argument("--tolerance", type=int, default=0)
    ap.add_argument("--variants", help="JSON file: {name: {hex: hex | hue/sat/val}}")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    variants = {}
    if a.variants:
        variants = json.load(open(a.variants))
    else:
        spec = {}
        if a.map:
            raw = a.map
            if os.path.isfile(raw):
                try:
                    raw = open(raw, encoding="utf-8").read()
                except UnicodeDecodeError as e:
                    raise GstInputError("palette map file is not valid UTF-8") from e
            spec.update(parse_map(raw))
        if a.src and a.dst:
            for s, d in zip(read_palette(a.src), read_palette(a.dst)):
                spec["%02x%02x%02x" % s] = "%02x%02x%02x" % d
        if a.hue or a.sat != 1.0 or a.val != 1.0:
            spec.update(hue=a.hue, sat=a.sat, val=a.val)
        if not spec:
            ap.error("give --map, --from/--to, --hue/--sat/--val or --variants")
        variants = {"swap": spec}
    n = 0
    for path in a.inputs:
        img = Image.open(path).convert("RGBA")
        base = os.path.splitext(os.path.basename(path))[0]
        for name, spec in variants.items():
            out = os.path.join(a.outdir, f"{base}_{name}.png" if a.variants or len(variants) > 1 else f"{base}_swap.png")
            if os.path.abspath(out) == os.path.abspath(path) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
            apply_variant(img, spec, a.tolerance).save(out)
            n += 1
    print(f"wrote {n} recoloured image(s) to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
