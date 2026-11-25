#!/usr/bin/env python3
"""sprite-angles: bake a sprite at N rotation angles (8-dir / 16-dir, or any --angles count) as a sheet plus atlas JSON.
Angle 0 is the original orientation; further frames rotate clockwise (use --ccw to go the other way) in equal steps
of 360/N degrees. Each frame is drawn onto a canvas large enough for the diagonal so nothing is clipped, with the
pivot at the centre (or --pivot feet / top-left). Nearest-neighbour by default (--linear for smooth). The atlas JSON
follows the same frame/spriteSourceSize/sourceSize layout as atlas-pack.
"""
import argparse, os, json, math, sys

from PIL import Image

def pack(frames, pad=1):
    w, h = frames[0].size
    # one row if few, otherwise a near-square grid
    cols = len(frames) if len(frames) <= 8 else math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols * (w + pad) - pad, rows * (h + pad) - pad), (0, 0, 0, 0))
    recs = []
    for i, im in enumerate(frames):
        x, y = (i % cols) * (w + pad), (i // cols) * (h + pad)
        sheet.paste(im, (x, y))
        recs.append((x, y, im.width, im.height))
    return sheet, recs


def rotate_frame(im, deg, pivot, resample):
    """Rotate around the named pivot and paste onto a diagonal-sized canvas, centred on that pivot."""
    w, h = im.size
    if pivot == "feet": px, py = w / 2, h
    elif pivot == "top-left": px, py = 0, 0
    else: px, py = w / 2, h / 2
    side = int(math.ceil(math.hypot(w, h))) + 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    # place so pivot lands at the canvas centre
    canvas.paste(im, (int(round(side / 2 - px)), int(round(side / 2 - py))), im)
    return canvas.rotate(-deg, resample=resample, expand=False, fillcolor=(0, 0, 0, 0), center=(side / 2, side / 2))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake a sprite at N rotation angles as a sheet plus atlas JSON.")
    ap.add_argument("image"); ap.add_argument("-o", "--out", required=True, help="output sheet PNG (JSON is this path with .json)")
    ap.add_argument("--angles", type=int, default=8); ap.add_argument("--ccw", action="store_true")
    ap.add_argument("--linear", action="store_true"); ap.add_argument("--pivot", choices=("centre", "center", "feet", "top-left"), default="centre")
    ap.add_argument("--prefix", help="frame name prefix (default: image stem)")
    ap.add_argument("--pad", type=int, default=1)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if getattr(a, 'out', None) and os.path.abspath(a.out) == os.path.abspath(a.image) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if a.angles < 1: sys.exit("--angles must be >= 1")
    im = Image.open(a.image).convert("RGBA")
    pivot = "centre" if a.pivot == "center" else a.pivot
    resample = Image.BILINEAR if a.linear else Image.NEAREST
    step = 360.0 / a.angles
    frames, angles = [], []
    for i in range(a.angles):
        deg = (-i if a.ccw else i) * step
        frames.append(rotate_frame(im, deg, pivot, resample)); angles.append(deg % 360)
    # make every frame the same size (they already are: diagonal canvas)
    sheet, recs = pack(frames, a.pad)
    prefix = a.prefix or os.path.splitext(os.path.basename(a.image))[0]
    atlas = {"frames": {}, "meta": {"image": os.path.basename(a.out), "size": {"w": sheet.width, "h": sheet.height},
                                    "angles": angles, "pivot": pivot, "scale": "1"}}
    for i, ((x, y, w, h), deg) in enumerate(zip(recs, angles)):
        name = f"{prefix}_{i:03d}"
        atlas["frames"][name] = {"frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                 "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
                                 "sourceSize": {"w": w, "h": h}, "angle": deg}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    sheet.save(a.out)
    js = os.path.splitext(a.out)[0] + ".json"; json.dump(atlas, open(js, "w"), indent=1)
    print(f"{a.angles} angle(s), sheet {sheet.width}x{sheet.height} -> {a.out}, {js}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
