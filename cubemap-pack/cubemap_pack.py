#!/usr/bin/env python3
"""cubemap-pack: pack six cube faces (px, nx, py, ny, pz, nz) into a horizontal strip,
vertical strip, or vertical cross, and unpack a strip or cross back to six faces. All
faces must be square and the same size. Writes new files; inputs are never overwritten
unless `--in-place`.
"""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402
from PIL import Image

FACES = ("px", "nx", "py", "ny", "pz", "nz")
# vertical cross, 4 cells wide x 3 tall:
#     py
# nx  pz  px  nz
#     ny
CROSS = {
    "py": (1, 0),
    "nx": (0, 1), "pz": (1, 1), "px": (2, 1), "nz": (3, 1),
    "ny": (1, 2),
}


def load_face(path):
    im = Image.open(path).convert("RGBA")
    if im.width != im.height:
        raise SystemExit(f"face must be square: {path} is {im.width}x{im.height}")
    return im


def pack(faces, layout):
    sizes = {n: faces[n].size for n in FACES}
    s = faces["px"].width
    if any(faces[n].size != (s, s) for n in FACES):
        raise SystemExit("all six faces must be the same size, got " +
                         ", ".join(f"{n}={sizes[n][0]}x{sizes[n][1]}" for n in FACES))
    if layout == "horizontal":
        out = Image.new("RGBA", (s * 6, s), (0, 0, 0, 0))
        for i, n in enumerate(FACES):
            out.paste(faces[n], (i * s, 0))
    elif layout == "vertical":
        out = Image.new("RGBA", (s, s * 6), (0, 0, 0, 0))
        for i, n in enumerate(FACES):
            out.paste(faces[n], (0, i * s))
    else:
        out = Image.new("RGBA", (s * 4, s * 3), (0, 0, 0, 0))
        for n, (cx, cy) in CROSS.items():
            out.paste(faces[n], (cx * s, cy * s))
    return out


def detect(w, h):
    if w == h * 6:
        return "horizontal", h
    if h == w * 6:
        return "vertical", w
    if w * 3 == h * 4 and w % 4 == 0:
        return "cross", w // 4
    raise SystemExit(f"cannot detect cubemap layout from {w}x{h} "
                     "(expected 6x1, 1x6, or 4x3 vertical cross)")


def unpack(im, layout=None):
    im = im.convert("RGBA")
    layout, s = (layout, { "horizontal": im.height, "vertical": im.width, "cross": im.width // 4 }[layout]) if layout else detect(im.width, im.height)
    if layout == "horizontal" and im.size != (s * 6, s):
        raise SystemExit(f"horizontal strip expected {s*6}x{s}, got {im.width}x{im.height}")
    if layout == "vertical" and im.size != (s, s * 6):
        raise SystemExit(f"vertical strip expected {s}x{s*6}, got {im.width}x{im.height}")
    if layout == "cross" and im.size != (s * 4, s * 3):
        raise SystemExit(f"cross expected {s*4}x{s*3}, got {im.width}x{im.height}")
    faces = {}
    if layout == "horizontal":
        for i, n in enumerate(FACES):
            faces[n] = im.crop((i * s, 0, (i + 1) * s, s))
    elif layout == "vertical":
        for i, n in enumerate(FACES):
            faces[n] = im.crop((0, i * s, s, (i + 1) * s))
    else:
        for n, (cx, cy) in CROSS.items():
            faces[n] = im.crop((cx * s, cy * s, (cx + 1) * s, (cy + 1) * s))
    return layout, s, faces


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pack or unpack six cube-map faces.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    for n in FACES:
        p.add_argument(f"--{n}", required=True, help=f"{n} face image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--layout", choices=("horizontal", "vertical", "cross"), default="horizontal")
    u = sub.add_parser("unpack")
    u.add_argument("input")
    u.add_argument("-o", "--outdir", required=True)
    u.add_argument("--layout", choices=("horizontal", "vertical", "cross"),
                   help="force a layout (default: detect from aspect ratio)")
    u.add_argument("--prefix", default="", help="prepended to each face filename")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.cmd == "pack":
        srcs = [getattr(a, n) for n in FACES]
        safe_out.check_any(srcs, a.out, a.in_place)
        faces = {n: load_face(getattr(a, n)) for n in FACES}
        out = pack(faces, a.layout)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        out.save(a.out)
        print(f"{a.layout} {out.width}x{out.height} -> {a.out}")
        return 0
    safe_out.check(a.input, a.outdir, a.in_place)
    layout, s, faces = unpack(Image.open(a.input), a.layout)
    os.makedirs(a.outdir, exist_ok=True)
    for n, im in faces.items():
        dest = os.path.join(a.outdir, f"{a.prefix}{n}.png")
        safe_out.check(a.input, dest, a.in_place)
        im.save(dest)
    print(f"unpacked {layout} ({s}x{s}) -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
