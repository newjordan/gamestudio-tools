#!/usr/bin/env python3
"""texture-resize: batch-resize images to a max edge, a power-of-two, and/or a multiple-of-N, with a before/after report.
Default filter is nearest-neighbour (pixel art); --linear uses bilinear. Does not upscale unless --allow-upscale.
--pot rounds each side down to the previous power of two (or up with --pot-up). --multiple N snaps down (or up with
--multiple-up). Writes into --outdir under the same names; refuses to overwrite inputs in place. JSON/CSV report.
"""
import argparse, os, csv, json, math, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402


def collect(paths):
    exts = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp", ".gif"}
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p) if os.path.splitext(f)[1].lower() in exts))
        elif os.path.splitext(p)[1].lower() in exts:
            out.append(p)
        else:
            raise SystemExit(f"not an image or folder: {p}")
    return out


def snap_pot(n, up):
    if n <= 1: return 1
    if up:
        return 1 << math.ceil(math.log2(n))
    return 1 << math.floor(math.log2(n))


def snap_mult(n, m, up):
    if m <= 0: return n
    if up: return int(math.ceil(n / m) * m)
    return max(m, int(math.floor(n / m) * m))


def target_size(w, h, max_edge, pot, pot_up, multiple, multiple_up, allow_up):
    nw, nh = w, h
    if max_edge and max(w, h) > max_edge:
        s = max_edge / max(w, h); nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    if pot:
        nw, nh = snap_pot(nw, pot_up), snap_pot(nh, pot_up)
    if multiple:
        nw, nh = snap_mult(nw, multiple, multiple_up), snap_mult(nh, multiple, multiple_up)
    if not allow_up:
        nw, nh = min(nw, w), min(nh, h)
        if pot:  # after clamping, re-snap down so we still honour pot/multiple
            nw, nh = snap_pot(max(1, nw), False), snap_pot(max(1, nh), False)
        if multiple:
            nw, nh = snap_mult(max(1, nw), multiple, False), snap_mult(max(1, nh), multiple, False)
    return max(1, nw), max(1, nh)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Batch-resize textures to a max size, power-of-two, or multiple.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--max", dest="max_edge", type=int, help="max edge in pixels")
    ap.add_argument("--pot", action="store_true"); ap.add_argument("--pot-up", action="store_true")
    ap.add_argument("--multiple", type=int); ap.add_argument("--multiple-up", action="store_true")
    ap.add_argument("--linear", action="store_true"); ap.add_argument("--allow-upscale", action="store_true")
    ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = collect(a.inputs)
    if not files: sys.exit("no images found")
    os.makedirs(a.outdir, exist_ok=True)
    filt = Image.BILINEAR if a.linear else Image.NEAREST
    rows = []
    for f in files:
        dest = os.path.join(a.outdir, os.path.basename(f))
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit(f"refusing to overwrite input {f}; pick a different --outdir or pass --in-place")
        try:
            im = Image.open(f)
            nw, nh = target_size(im.width, im.height, a.max_edge, a.pot, a.pot_up, a.multiple, a.multiple_up, a.allow_upscale)
            out = im if (nw, nh) == (im.width, im.height) else im.resize((nw, nh), filt)
            out.save(dest)
        except GstInputError:
            raise
        except MemoryError as e:
            raise GstInputError("image is too large") from e
        except ValueError as e:
            raise GstInputError("image file is not valid: %s" % e) from e
        rec = {"file": f, "out": dest, "src_w": im.width, "src_h": im.height, "dst_w": nw, "dst_h": nh,
               "changed": (nw, nh) != (im.width, im.height)}
        rows.append(rec)
        print(f"{os.path.basename(f)}: {im.width}x{im.height} -> {nw}x{nh}" + ("" if rec["changed"] else " (unchanged)"))
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv:
        cols = ["file", "src_w", "src_h", "dst_w", "dst_h", "changed", "out"]
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} file(s), {sum(r['changed'] for r in rows)} resized -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
