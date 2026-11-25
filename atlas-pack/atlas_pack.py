#!/usr/bin/env python3
"""atlas-pack: pack a folder of sprites into one texture atlas (PNG + JSON).

Custom MaxRects (best-short-side-fit) packer written for OmniSpace.
Algorithm reference: J. Jylanki, "A Thousand Ways to Pack the Bin" (2010).
"""
import argparse, os, json, sys
from PIL import Image


class MaxRects:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.free = [(0, 0, w, h)]

    def insert(self, rw, rh):
        best = None
        for fx, fy, fw, fh in self.free:
            if rw <= fw and rh <= fh:
                short = min(fw - rw, fh - rh)
                long_ = max(fw - rw, fh - rh)
                if best is None or (short, long_) < best[0]:
                    best = ((short, long_), (fx, fy, rw, rh))
        if best is None:
            return None
        node = best[1]
        self._split(node)
        return node

    def _split(self, used):
        ux, uy, uw, uh = used
        out = []
        for f in self.free:
            fx, fy, fw, fh = f
            if ux >= fx + fw or ux + uw <= fx or uy >= fy + fh or uy + uh <= fy:
                out.append(f)
                continue
            if ux > fx:
                out.append((fx, fy, ux - fx, fh))
            if ux + uw < fx + fw:
                out.append((ux + uw, fy, fx + fw - ux - uw, fh))
            if uy > fy:
                out.append((fx, fy, fw, uy - fy))
            if uy + uh < fy + fh:
                out.append((fx, uy + uh, fw, fy + fh - uy - uh))
        # prune contained rects
        pruned = []
        for i, a in enumerate(out):
            contained = False
            for j, b in enumerate(out):
                if i != j and a[0] >= b[0] and a[1] >= b[1] and a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3]:
                    if a != b or i > j:
                        contained = True
                        break
            if not contained:
                pruned.append(a)
        self.free = pruned


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402

def trim(img):
    bbox = img.getchannel("A").getbbox() if img.mode == "RGBA" else None
    if not bbox:
        return img, (0, 0, img.width, img.height)
    return img.crop(bbox), bbox


def pack(paths, max_size=4096, padding=2, do_trim=True, pot=True):
    items = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        src_w, src_h = im.size
        bbox = (0, 0, src_w, src_h)
        if do_trim:
            im, bbox = trim(im)
        items.append({"name": os.path.splitext(os.path.basename(p))[0], "img": im,
                      "src": (src_w, src_h), "bbox": bbox})
    items.sort(key=lambda it: max(it["img"].size), reverse=True)
    size = 64
    while size <= max_size:
        mr = MaxRects(size, size)
        placed = []
        ok = True
        for it in items:
            w, h = it["img"].size
            node = mr.insert(w + padding, h + padding)
            if node is None:
                ok = False
                break
            placed.append((it, node))
        if ok:
            break
        size *= 2
    else:
        raise SystemExit(f"Sprites do not fit in {max_size}x{max_size}")
    used_w = max(n[0] + n[2] for _, n in placed) if placed else 1
    used_h = max(n[1] + n[3] for _, n in placed) if placed else 1
    if pot:
        aw = ah = size
    else:
        aw, ah = used_w, used_h
    atlas = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
    frames = {}
    for it, (x, y, _, _) in placed:
        atlas.paste(it["img"], (x, y))
        w, h = it["img"].size
        bx, by, _, _ = it["bbox"]
        frames[it["name"]] = {"frame": {"x": x, "y": y, "w": w, "h": h},
                              "trimmed": (w, h) != it["src"],
                              "spriteSourceSize": {"x": bx, "y": by, "w": w, "h": h},
                              "sourceSize": {"w": it["src"][0], "h": it["src"][1]}}
    return atlas, frames


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pack sprites into a texture atlas.")
    ap.add_argument("input", help="folder of PNGs (or a single file list via @list.txt)")
    ap.add_argument("-o", "--out", default="atlas", help="output basename (writes .png and .json)")
    ap.add_argument("--max", type=int, default=4096, help="max atlas side")
    ap.add_argument("--padding", type=int, default=2)
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--no-pot", action="store_true", help="crop atlas to used area instead of power-of-two")
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

    if a.input.startswith("@"):
        paths = [l.strip() for l in open(a.input[1:]) if l.strip()]
    elif os.path.isdir(a.input):
        paths = sorted(os.path.join(a.input, f) for f in os.listdir(a.input) if f.lower().endswith(".png"))
    else:
        raise GstInputError("atlas-pack needs a directory of images, not a file")
    if not paths:
        sys.exit("no PNGs found")
    for dest in (a.out + ".png", a.out + ".json"):
        for src in paths + [a.input]:
            if os.path.abspath(dest) == os.path.abspath(src) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    atlas, frames = pack(paths, a.max, a.padding, not a.no_trim, not a.no_pot)
    atlas.save(a.out + ".png")
    meta = {"frames": frames, "meta": {"image": os.path.basename(a.out) + ".png",
            "size": {"w": atlas.width, "h": atlas.height}, "app": "omnispace atlas-pack", "format": "RGBA8888"}}
    with open(a.out + ".json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"packed {len(frames)} sprites into {atlas.width}x{atlas.height} -> {a.out}.png/.json")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
