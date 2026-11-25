#!/usr/bin/env python3
"""nine-slice: preview and bake a 9-slice (9-patch) image, the usual way UI panels and speech bubbles stretch.
Insets are --insets L,T,R,B in pixels, or --center X,Y,W,H (the stretchable middle rectangle). The four corners are
copied, the four edges stretch in one axis and the centre in both. --preview writes a contact sheet of the patch at
several sizes (default 0.5x, 1x, 1.5x, 2x of the source, plus any --size). --size WxH also writes a single stretched
PNG. Reports the insets and flags a --size that is smaller than the corners (the edges would overlap). The source is
never overwritten. Pixel art should be stretched with --nearest (default); --linear is for painted panels.
"""
import argparse, os, json, sys

from PIL import Image


def insets_of(w, h, insets=None, center=None):
    if center:
        x, y, cw, ch = center
        l, t, r, b = x, y, w - (x + cw), h - (y + ch)
    else:
        l, t, r, b = insets
    if min(l, t, r, b) < 0 or l + r >= w or t + b >= h:
        raise SystemExit(f"insets L{l} T{t} R{r} B{b} leave no stretchable centre in a {w}x{h} image")
    return int(l), int(t), int(r), int(b)


def patches(im, L, T, R, B):
    w, h = im.size; cx, cy = w - L - R, h - T - B
    def c(x, y, ww, hh): return im.crop((x, y, x + ww, y + hh))
    return {"nw": c(0, 0, L, T), "n": c(L, 0, cx, T), "ne": c(w - R, 0, R, T),
            "w": c(0, T, L, cy), "c": c(L, T, cx, cy), "e": c(w - R, T, R, cy),
            "sw": c(0, h - B, L, B), "s": c(L, h - B, cx, B), "se": c(w - R, h - B, R, B)}


def stretch(im, L, T, R, B, tw, th, nearest=True):
    if tw < L + R or th < T + B:
        raise SystemExit(f"target {tw}x{th} is smaller than the corners ({L + R}x{T + B})")
    filt = Image.NEAREST if nearest else Image.BILINEAR
    p = patches(im, L, T, R, B); cw, ch = tw - L - R, th - T - B
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    def place(name, xy, size=None):
        if size is not None and (size[0] <= 0 or size[1] <= 0): return
        tile = p[name] if size is None else p[name].resize(size, filt); out.paste(tile, xy, tile)
    place("nw", (0, 0)); place("n", (L, 0), (cw, T)); place("ne", (tw - R, 0))
    place("w", (0, T), (L, ch)); place("c", (L, T), (cw, ch)); place("e", (tw - R, T), (R, ch))
    place("sw", (0, th - B)); place("s", (L, th - B), (cw, B)); place("se", (tw - R, th - B))
    return out


def preview(im, L, T, R, B, sizes, nearest=True, pad=8, bg=(40, 40, 48)):
    tiles = [stretch(im, L, T, R, B, w, h, nearest) for w, h in sizes]
    W = sum(t.width for t in tiles) + pad * (len(tiles) + 1); H = max(t.height for t in tiles) + pad * 2
    sheet = Image.new("RGBA", (W, H), bg + (255,)); x = pad
    for t in tiles: sheet.alpha_composite(t, (x, pad)); x += t.width + pad
    return sheet


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preview or bake a 9-slice (9-patch) image.")
    ap.add_argument("image"); ap.add_argument("--insets", help="L,T,R,B in pixels"); ap.add_argument("--center", help="X,Y,W,H of the stretchable middle")
    ap.add_argument("--preview", help="contact-sheet PNG of several sizes"); ap.add_argument("--size", help="WxH of a single baked PNG")
    ap.add_argument("-o", "--out", help="path for --size output"); ap.add_argument("--linear", action="store_true")
    ap.add_argument("--sizes", help="comma list of WxH for the preview (default: 0.5x,1x,1.5x,2x plus --size)")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    for _src, _dst in ((a.image, a.out), (a.image, getattr(a, 'preview', None))):
        if _dst and os.path.abspath(_dst) == os.path.abspath(_src) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    im = Image.open(a.image).convert("RGBA"); w, h = im.size
    if a.center: insets = insets_of(w, h, center=[int(x) for x in a.center.split(",")])
    elif a.insets: insets = insets_of(w, h, insets=[int(x) for x in a.insets.split(",")])
    else: sys.exit("give --insets L,T,R,B or --center X,Y,W,H")
    L, T, R, B = insets; nearest = not a.linear
    baked = None
    if a.size:
        tw, th = (int(x) for x in a.size.lower().split("x"))
        if not a.out: sys.exit("--size needs -o")
        baked = stretch(im, L, T, R, B, tw, th, nearest); baked.save(a.out); print(f"baked {tw}x{th} -> {a.out}")
    if a.preview:
        if a.sizes: sizes = [tuple(int(x) for x in s.lower().split("x")) for s in a.sizes.split(",")]
        else:
            sizes = [(max(L + R, int(w * s)), max(T + B, int(h * s))) for s in (0.5, 1.0, 1.5, 2.0)]
            if a.size: sizes.append(tuple(int(x) for x in a.size.lower().split("x")))
        preview(im, L, T, R, B, sizes, nearest).save(a.preview); print(f"preview {len(sizes)} size(s) -> {a.preview}")
    if not a.preview and not a.size: sys.exit("give --preview and/or --size")
    if a.json: json.dump({"insets": {"l": L, "t": T, "r": R, "b": B}, "source": [w, h], "min_size": [L + R, T + B]}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
