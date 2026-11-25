#!/usr/bin/env python3
"""sprite-sheet-optimize: shrink an existing sprite sheet / atlas. Reads an atlas PNG plus its JSON (atlas-pack's
hash layout, or the common array layout with "filename"), then
  1. cuts every frame out and trims transparent borders (offsets kept in spriteSourceSize),
  2. finds frames whose trimmed pixels are identical and stores them once (all names still resolve),
  3. repacks with MaxRects (from atlas-pack) trying many sheet widths and keeping the smallest area,
and writes a new PNG + JSON in atlas-pack's layout with an "alias_of" field on shared frames.
Rotated frames ("rotated": true) are refused rather than guessed at. Pixels are never resampled.
"""
import argparse, os, json, sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "atlas-pack"))
import atlas_pack  # noqa: E402


def load_frames(meta):
    fr = meta.get("frames")
    if isinstance(fr, dict):
        items = list(fr.items())
    elif isinstance(fr, list):
        items = [(f.get("filename") or f.get("name") or str(i), f) for i, f in enumerate(fr)]
    else:
        raise SystemExit("JSON has no 'frames'")
    out = []
    for name, f in items:
        if f.get("rotated"): raise SystemExit(f"frame {name!r} is rotated; this tool does not un-rotate frames")
        r = f["frame"]
        src = f.get("sourceSize") or {"w": r["w"], "h": r["h"]}
        sss = f.get("spriteSourceSize") or {"x": 0, "y": 0, "w": r["w"], "h": r["h"]}
        out.append({"name": name, "rect": (r["x"], r["y"], r["w"], r["h"]), "src": (src["w"], src["h"]), "off": (sss["x"], sss["y"])})
    return out


def cut(sheet, frames):
    """-> list of dicts with the trimmed RGBA array and the offset inside the original source rectangle."""
    a = np.array(sheet.convert("RGBA")); res = []
    for f in frames:
        x, y, w, h = f["rect"]
        if x < 0 or y < 0 or x + w > a.shape[1] or y + h > a.shape[0]: raise SystemExit(f"frame {f['name']!r} lies outside the sheet")
        t = a[y:y + h, x:x + w].copy(); ox, oy = f["off"]
        ys, xs = np.where(t[..., 3] > 0)
        if len(xs) == 0:                       # fully transparent frame: keep a 1x1 transparent pixel so it still has a rect
            t = np.zeros((1, 1, 4), np.uint8); bx = by = 0
        else:
            bx, by = int(xs.min()), int(ys.min()); t = t[by:int(ys.max()) + 1, bx:int(xs.max()) + 1].copy()
        res.append({"name": f["name"], "img": t, "src": f["src"], "off": (ox + bx, oy + by)})
    return res


def dedupe(cuts):
    seen, uniq = {}, []
    for c in cuts:
        k = c["img"].copy(); k[k[..., 3] == 0] = 0     # invisible pixels never make frames "different"
        key = (k.shape, k.tobytes())
        if key in seen: c["alias"] = uniq[seen[key]]["name"]; c["uid"] = seen[key]
        else: seen[key] = len(uniq); c["uid"] = len(uniq); uniq.append(c); c["alias"] = None
    return uniq


def layout(uniq, padding, pot, max_size, max_width=None):
    """Try many widths; return (W, H, placements) with the smallest area (ties: squarer)."""
    if not uniq: return 1, 1, []
    items = sorted(range(len(uniq)), key=lambda i: (-max(uniq[i]["img"].shape[:2]), -uniq[i]["img"].shape[0] * uniq[i]["img"].shape[1], i))
    wmin = max(u["img"].shape[1] for u in uniq) + padding
    total = sum((u["img"].shape[0] + padding) * (u["img"].shape[1] + padding) for u in uniq)
    if max_width is not None and max_width < wmin: raise SystemExit(f"--max-width {max_width} is smaller than the widest frame plus padding ({wmin})")
    wmax = min(max_size, max_width or max_size, max(wmin, int(total ** 0.5 * 3)))
    cands = sorted({wmin, wmax} | {w for w in range(wmin, wmax + 1, max(1, (wmax - wmin) // 40 or 1))} | {2 ** k for k in range(4, 14) if wmin <= 2 ** k <= wmax})
    best = None
    for W in cands:
        mr = atlas_pack.MaxRects(W, max_size); place = {}; ok = True
        for i in items:
            h, w = uniq[i]["img"].shape[:2]; node = mr.insert(w + padding, h + padding)
            if node is None: ok = False; break
            place[i] = (node[0], node[1])
        if not ok: continue
        H = max(place[i][1] + uniq[i]["img"].shape[0] for i in place); Wu = max(place[i][0] + uniq[i]["img"].shape[1] for i in place)
        if pot: Wf, Hf = 1 << (Wu - 1).bit_length(), 1 << (H - 1).bit_length()
        else: Wf, Hf = Wu, H
        score = (Wf * Hf, abs(Wf - Hf))
        if best is None or score < best[0]: best = (score, Wf, Hf, place)
    if best is None: raise SystemExit(f"frames do not fit within {max_size}px")
    return best[1], best[2], best[3]


def optimize(sheet, meta, padding=1, pot=False, max_size=4096, dedupe_frames=True, max_width=None):
    cuts = cut(sheet, load_frames(meta))
    if dedupe_frames: uniq = dedupe(cuts)
    else:
        uniq = cuts
        for i, c in enumerate(cuts): c["uid"] = i; c["alias"] = None
    W, H, place = layout(uniq, padding, pot, max_size, max_width)
    out = np.zeros((H, W, 4), np.uint8)
    for i, (x, y) in place.items():
        im = uniq[i]["img"]; out[y:y + im.shape[0], x:x + im.shape[1]] = im
    frames = {}
    for c in cuts:
        x, y = place[c["uid"]]; h, w = c["img"].shape[:2]
        e = {"frame": {"x": x, "y": y, "w": w, "h": h}, "trimmed": (w, h) != tuple(c["src"]),
             "spriteSourceSize": {"x": c["off"][0], "y": c["off"][1], "w": w, "h": h}, "sourceSize": {"w": c["src"][0], "h": c["src"][1]}}
        if c["alias"]: e["alias_of"] = c["alias"]
        frames[c["name"]] = e
    stats = {"frames": len(cuts), "unique": len(uniq), "before": list(sheet.size), "after": [W, H],
             "area_before": sheet.size[0] * sheet.size[1], "area_after": W * H}
    return Image.fromarray(out, "RGBA"), frames, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trim, dedupe and repack a sprite sheet to the smallest area.")
    ap.add_argument("json", help="atlas JSON (frames dict or array)"); ap.add_argument("--image", help="atlas PNG (default: meta.image next to the JSON)")
    ap.add_argument("-o", "--out", default="optimized", help="output basename (writes .png and .json)")
    ap.add_argument("--padding", type=int, default=1); ap.add_argument("--pot", action="store_true", help="round the sheet up to powers of two")
    ap.add_argument("--max", type=int, default=4096); ap.add_argument("--max-width", type=int, help="never make the sheet wider than this (e.g. for a texture limit or a squarer layout)"); ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    for _cand in (a.out, a.out + '.png', a.out + '.json'):
        if os.path.abspath(_cand) == os.path.abspath(a.json) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    meta = json.load(open(a.json))
    img = a.image or os.path.join(os.path.dirname(os.path.abspath(a.json)), (meta.get("meta") or {}).get("image", ""))
    if not os.path.isfile(img): sys.exit(f"atlas image not found: {img} (use --image)")
    sheet = Image.open(img)
    im, frames, st = optimize(sheet, meta, a.padding, a.pot, a.max, not a.no_dedupe, a.max_width)
    im.save(a.out + ".png")
    json.dump({"frames": frames, "meta": {"image": os.path.basename(a.out) + ".png", "size": {"w": im.width, "h": im.height}, "app": "gst sprite-sheet-optimize", "format": "RGBA8888"}}, open(a.out + ".json", "w"), indent=2)
    pct = 100 * (1 - st["area_after"] / st["area_before"]) if st["area_before"] else 0
    print(f"{st['frames']} frames ({st['unique']} unique): {st['before'][0]}x{st['before'][1]} -> {st['after'][0]}x{st['after'][1]} ({pct:.0f}% less area) -> {a.out}.png/.json")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
