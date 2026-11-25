#!/usr/bin/env python3
"""sheet-pad: add padding (and optional alpha bleed) between already-packed frames in a sprite sheet, rewriting the
atlas JSON (atlas-pack / TexturePacker hash or array format). Frames are re-shelved in (y, x) order with --pad pixels
on every side; --keep-layout inflates the existing positions instead. Rotated frames are refused. The input sheet and
JSON are never overwritten.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alpha-bleed"))
import alpha_bleed  # noqa: E402


def load_atlas(path):
    data = json.load(open(path, encoding="utf-8"))
    frames = data.get("frames")
    if frames is None: sys.exit("atlas JSON has no frames")
    if isinstance(frames, list):
        items = [(f.get("filename") or f.get("name") or f.get("id") or str(i), f) for i, f in enumerate(frames)]
    else:
        items = list(frames.items())
    return data, items


def frame_rect(rec):
    fr = rec.get("frame") or rec
    try:
        return int(fr["x"]), int(fr["y"]), int(fr["w"]), int(fr["h"])
    except KeyError:
        sys.exit("atlas frame is missing x/y/w/h")


def shelf_pack(sizes, pad, max_w=None):
    """sizes: list of (key, w, h). Returns placements {key: (x,y)}, sheet size."""
    if max_w is None:
        cell = [w + 2 * pad for _, w, h in sizes] or [2 * pad]
        area = sum((w + 2 * pad) * (h + 2 * pad) for _, w, h in sizes)
        max_w = max(max(cell), int(area ** 0.5) or 1)
    x = y = row_h = width = 0
    place = {}
    for key, w, h in sizes:
        fw, fh = w + 2 * pad, h + 2 * pad
        if x > 0 and x + fw > max_w:
            y += row_h; x = 0; row_h = 0
        place[key] = (x + pad, y + pad)
        x += fw
        row_h = max(row_h, fh)
        width = max(width, x)
    return place, (max(width, 1), max(y + row_h, 1))


def inflate_layout(boxes, pad):
    """boxes: list of (key, x, y, w, h). Inflate unique x/y ranks by pad."""
    xs = sorted({b[1] for b in boxes})
    ys = sorted({b[2] for b in boxes})
    xi = {v: i for i, v in enumerate(xs)}
    yi = {v: i for i, v in enumerate(ys)}
    place, width, height = {}, 1, 1
    for key, x, y, w, h in boxes:
        nx, ny = x + pad * (xi[x] + 1), y + pad * (yi[y] + 1)
        place[key] = (nx, ny)
        width = max(width, nx + w + pad)
        height = max(height, ny + h + pad)
    return place, (width, height)


def rewrite_frame(rec, x, y, w, h):
    out = json.loads(json.dumps(rec))
    if "frame" in out:
        out["frame"] = {"x": x, "y": y, "w": w, "h": h}
    else:
        out["x"], out["y"], out["w"], out["h"] = x, y, w, h
    return out


def parse_bg(s):
    bg = s.lstrip("#")
    if len(bg) == 6: bg += "00"
    if len(bg) != 8: sys.exit("--bg must be #rrggbb or #rrggbbaa")
    return tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4, 6))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add padding (and optional bleed) between packed sprite-sheet frames.")
    ap.add_argument("sheet"); ap.add_argument("atlas")
    ap.add_argument("-o", "--out", required=True, help="output sheet PNG")
    ap.add_argument("--atlas-out", help="output atlas JSON (default: --out with .json)")
    ap.add_argument("--pad", type=int, default=1)
    ap.add_argument("--bleed", type=int, default=0, help="alpha-bleed distance into the pad (0 = off)")
    ap.add_argument("--keep-layout", action="store_true")
    ap.add_argument("--bg", default="#00000000")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.pad < 0 or a.bleed < 0: sys.exit("--pad and --bleed must be >= 0")
    atlas_out = a.atlas_out or (os.path.splitext(a.out)[0] + ".json")
    for src, dest in ((a.sheet, a.out), (a.atlas, atlas_out)):
        if os.path.abspath(src) == os.path.abspath(dest) and not a.in_place:
            sys.exit("refusing to overwrite an input; pick a different -o / --atlas-out or pass --in-place")
    data, items = load_atlas(a.atlas)
    sheet = Image.open(a.sheet).convert("RGBA")
    frames = []
    for name, rec in items:
        if rec.get("rotated"):
            sys.exit(f"rotated frames are not supported ({name})")
        x, y, w, h = frame_rect(rec)
        core = sheet.crop((x, y, x + w, y + h)).convert("RGBA")
        bled = None
        if a.bleed > 0:
            tmp = Image.new("RGBA", (w + 2 * a.bleed, h + 2 * a.bleed), (0, 0, 0, 0))
            tmp.paste(core, (a.bleed, a.bleed))
            bled, _ = alpha_bleed.bleed(tmp, distance=a.bleed)
        frames.append({"name": name, "rec": rec, "x": x, "y": y, "w": w, "h": h, "core": core, "bled": bled})
    if a.keep_layout:
        place, size = inflate_layout([(f["name"], f["x"], f["y"], f["w"], f["h"]) for f in frames], a.pad)
    else:
        ordered = sorted(frames, key=lambda f: (f["y"], f["x"], f["name"] or ""))
        place, size = shelf_pack([(f["name"], f["w"], f["h"]) for f in ordered], a.pad)
    out = Image.new("RGBA", size, parse_bg(a.bg))
    new_hash, new_list = {}, []
    was_list = isinstance(data.get("frames"), list)
    for f in frames:
        nx, ny = place[f["name"]]; w, h = f["w"], f["h"]
        if f["bled"] is not None:
            bx = min(a.bleed, a.pad)
            region = f["bled"].crop((a.bleed - bx, a.bleed - bx, a.bleed + w + bx, a.bleed + h + bx))
            out.paste(region, (nx - bx, ny - bx), region)
        else:
            out.paste(f["core"], (nx, ny), f["core"])
        rewritten = rewrite_frame(f["rec"], nx, ny, w, h)
        if was_list:
            rewritten.setdefault("filename", f["name"])
            new_list.append(rewritten)
        else:
            new_hash[f["name"]] = rewritten
    data = json.loads(json.dumps(data))
    data["frames"] = new_list if was_list else new_hash
    meta = data.setdefault("meta", {})
    meta["size"] = {"w": out.width, "h": out.height}
    meta["image"] = os.path.basename(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    out.save(a.out)
    json.dump(data, open(atlas_out, "w"), indent=1)
    print(f"{len(frames)} frame(s), pad {a.pad}, {out.width}x{out.height} -> {a.out} + {atlas_out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
