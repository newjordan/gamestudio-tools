#!/usr/bin/env python3
"""sprite-stack: composite named layers (body, outline, shadow, fx, ...) into one sprite
per stem. Inputs are either `{stem}.{layer}.png` in one folder (`--layout dotted`, default)
or `{layer}/{stem}.png` (`--layout folders`). Layers are pasted bottom-to-top in the order
given by `--layers`. Frames of different sizes share a canvas (max width/height) and are
aligned by `--anchor`. Writes a new directory of PNGs; inputs are never overwritten unless
`--in-place`.
"""
import argparse, os, json, sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

IMAGE_EXTS = {".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}


def anchors(cw, ch, w, h, anchor):
    a = (anchor or "bottom").lower().replace("_", "-")
    if a in ("top-left", "nw", "origin"):
        return 0, 0
    if a in ("top", "top-center", "n"):
        return (cw - w) // 2, 0
    if a in ("top-right", "ne"):
        return cw - w, 0
    if a in ("left", "w"):
        return 0, (ch - h) // 2
    if a in ("center", "centre", "middle"):
        return (cw - w) // 2, (ch - h) // 2
    if a in ("right", "e"):
        return cw - w, (ch - h) // 2
    if a in ("bottom-left", "sw"):
        return 0, ch - h
    if a in ("bottom-right", "se"):
        return cw - w, ch - h
    # bottom / bottom-center
    return (cw - w) // 2, ch - h


def collect_dotted(root, layers):
    # {stem}.{layer}.ext
    groups = {}
    for p in sorted(Path(root).iterdir()) if Path(root).is_dir() else []:
        if p.suffix.lower() not in IMAGE_EXTS or not p.is_file():
            continue
        name = p.stem
        for layer in layers:
            suffix = "." + layer
            if name.endswith(suffix):
                stem = name[: -len(suffix)]
                groups.setdefault(stem, {})[layer] = p
                break
    return groups


def collect_folders(root, layers):
    groups = {}
    root = Path(root)
    for layer in layers:
        d = root / layer
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in IMAGE_EXTS or not p.is_file():
                continue
            groups.setdefault(p.stem, {})[layer] = p
    return groups


def paste_layers(paths, order, anchor):
    images = []
    for layer in order:
        p = paths.get(layer)
        if p is None:
            continue
        im = Image.open(p).convert("RGBA")
        images.append((layer, im))
    if not images:
        return None
    cw = max(im.size[0] for _, im in images)
    ch = max(im.size[1] for _, im in images)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    for _layer, im in images:
        x, y = anchors(cw, ch, im.size[0], im.size[1], anchor)
        canvas.alpha_composite(im, (x, y))
    return canvas


def main(argv=None):
    ap = argparse.ArgumentParser(description="Composite named sprite layers into one image per stem.")
    ap.add_argument("input", help="folder of dotted-name frames, or a parent of per-layer folders")
    ap.add_argument("-o", "--out", required=True, help="output folder")
    ap.add_argument("--layers", required=True, help="comma list, bottom to top (e.g. shadow,body,outline,fx)")
    ap.add_argument("--layout", choices=("dotted", "folders"), default="dotted")
    ap.add_argument("--anchor", default="bottom", help="alignment when layer sizes differ (default: bottom)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    layers = [x.strip() for x in a.layers.split(",") if x.strip()]
    if not layers:
        sys.exit("--layers is empty")
    if not os.path.isdir(a.input):
        sys.exit(f"not a directory: {a.input}")
    groups = collect_dotted(a.input, layers) if a.layout == "dotted" else collect_folders(a.input, layers)
    if not groups:
        sys.exit("no layer images matched")
    sources = [str(p) for g in groups.values() for p in g.values()]
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    os.makedirs(a.out, exist_ok=True)
    written = []
    for stem in sorted(groups):
        dest = os.path.join(a.out, stem + ".png")
        safe_out.check_any([str(p) for p in groups[stem].values()], dest, a.in_place)
        im = paste_layers(groups[stem], layers, a.anchor)
        if im is None:
            continue
        im.save(dest)
        written.append({"stem": stem, "layers": sorted(groups[stem]), "path": dest,
                        "size": list(im.size)})
    rec = {"count": len(written), "layers": layers, "out": a.out, "files": written}
    print(f"{len(written)} sprite(s) -> {a.out}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
