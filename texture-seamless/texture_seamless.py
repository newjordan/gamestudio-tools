#!/usr/bin/env python3
"""texture-seamless: make a texture tile without visible seams (offset + blend), score the seams, and
write a 2x2 tiled preview. Method: roll the image by half its size so the old edges become an interior
cross, then blend the original back in with a smooth window that is 0 at the borders and 1 in the centre.
The new borders then come from pixels that were adjacent in the source, so left/right and top/bottom
edges continue each other. Trade-off: the centre cross region mixes two copies, so busy photographic
textures can show mild ghosting; --power sharpens the window to limit it.
"""
import os
import argparse
import numpy as np
from PIL import Image
import sys


def seam_score(a):
    """edge discontinuity relative to normal pixel-to-pixel change (about 1.0 = invisible, >>1 = visible seam)."""
    f = np.asarray(a, dtype=np.float64)
    inner_h = np.abs(np.diff(f, axis=1)).mean() + 1e-9
    inner_v = np.abs(np.diff(f, axis=0)).mean() + 1e-9
    wrap_h = np.abs(f[:, 0] - f[:, -1]).mean()
    wrap_v = np.abs(f[0] - f[-1]).mean()
    return float((wrap_h / inner_h + wrap_v / inner_v) / 2)


def make_seamless(img, power=1.0):
    a = np.asarray(img.convert("RGBA"), dtype=np.float64)
    h, w = a.shape[:2]
    shifted = np.roll(np.roll(a, h // 2, 0), w // 2, 1)
    wx = np.sin(np.pi * (np.arange(w) + 0.5) / w) ** power
    wy = np.sin(np.pi * (np.arange(h) + 0.5) / h) ** power
    W = (wy[:, None] * wx[None, :])[..., None]
    out = a * W + shifted * (1 - W)
    return Image.fromarray(out.round().clip(0, 255).astype(np.uint8), "RGBA")


def preview(img, n=2):
    out = Image.new("RGBA", (img.width * n, img.height * n))
    for y in range(n):
        for x in range(n):
            out.paste(img, (x * img.width, y * img.height))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make textures tile seamlessly.")
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--power", type=float, default=1.0, help="window sharpness (>1 keeps more of the original centre)")
    ap.add_argument("--preview", help="also write a 2x2 tiled preview PNG")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    src = Image.open(a.input).convert("RGBA")
    before = seam_score(np.array(src)[..., :3])
    out = make_seamless(src, a.power)
    out.save(a.out)
    after = seam_score(np.array(out)[..., :3])
    if a.preview: preview(out).save(a.preview)
    print(f"seam score {before:.2f} -> {after:.2f} (1.0 = invisible) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
