#!/usr/bin/env python3
"""sprite-flip-sheet: generate mirrored copies (horizontal, vertical, or both) of frames from a sheet plus atlas JSON,
writing a new sheet and atlas. Original frames are kept; flipped copies are named with a suffix (`_h`, `_v`, `_hv`).
Rotated frames are refused. The input is never overwritten.
"""
import argparse, os, json, sys

from PIL import Image


def load_atlas(path):
    data = json.load(open(path, encoding="utf-8"))
    frames = data.get("frames")
    if frames is None: sys.exit("atlas JSON has no frames")
    if isinstance(frames, list):
        items = [(f.get("filename") or f.get("name") or f.get("id") or str(i), f) for i, f in enumerate(frames)]
    else:
        items = list(frames.items())
    return data, items


def rect(rec):
    fr = rec.get("frame") or rec
    return int(fr["x"]), int(fr["y"]), int(fr["w"]), int(fr["h"])


def suffix_name(name, suf):
    if not name: return suf.lstrip("_")
    stem, ext = os.path.splitext(name)
    return stem + suf + ext


def rewrite(rec, x, y, w, h, filename=None):
    out = json.loads(json.dumps(rec))
    if "frame" in out:
        out["frame"] = {"x": x, "y": y, "w": w, "h": h}
    else:
        out["x"], out["y"], out["w"], out["h"] = x, y, w, h
    if filename is not None and "filename" in out:
        out["filename"] = filename
    # flipped sprites: spriteSourceSize x may need mirroring if trimmed. Leave it; gap is documented.
    return out


def pack(cells, pad=0, columns=None):
    if not cells: return {}, (1, 1)
    max_w = max(im.width for _, im, _ in cells)
    if not columns:
        columns = max(1, int(len(cells) ** 0.5 + 0.5))
    x = y = row_h = width = 0
    col = 0
    place = {}
    for name, im, rec in cells:
        if col >= columns:
            y += row_h + pad; x = 0; row_h = 0; col = 0
        place[name] = (x, y, im, rec)
        x += im.width + pad
        width = max(width, x - pad)
        row_h = max(row_h, im.height)
        col += 1
    return place, (max(width, 1), max(y + row_h, 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add mirrored frames to a sprite sheet and rewrite the atlas JSON.")
    ap.add_argument("sheet"); ap.add_argument("atlas")
    ap.add_argument("-o", "--out", required=True, help="output sheet PNG")
    ap.add_argument("--atlas-out")
    ap.add_argument("--horizontal", action="store_true")
    ap.add_argument("--vertical", action="store_true")
    ap.add_argument("--both", action="store_true", help="also write the HV combination (implies H and V)")
    ap.add_argument("--pad", type=int, default=0)
    ap.add_argument("--columns", type=int)
    ap.add_argument("--bg", default="#00000000")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if not (a.horizontal or a.vertical or a.both):
        a.horizontal = True
    if a.both:
        a.horizontal = a.vertical = True
    atlas_out = a.atlas_out or (os.path.splitext(a.out)[0] + ".json")
    for src, dest in ((a.sheet, a.out), (a.atlas, atlas_out)):
        if os.path.abspath(src) == os.path.abspath(dest) and not a.in_place:
            sys.exit("refusing to overwrite an input; pick a different -o / --atlas-out or pass --in-place")
    data, items = load_atlas(a.atlas)
    sheet = Image.open(a.sheet).convert("RGBA")
    cells = []  # (name, im, rec)
    for name, rec in items:
        if rec.get("rotated"): sys.exit(f"rotated frames are not supported ({name})")
        x, y, w, h = rect(rec)
        im = sheet.crop((x, y, x + w, y + h)).convert("RGBA")
        cells.append((name, im, rec))
        if a.horizontal:
            cells.append((suffix_name(name, "_h"), im.transpose(Image.Transpose.FLIP_LEFT_RIGHT), rec))
        if a.vertical:
            cells.append((suffix_name(name, "_v"), im.transpose(Image.Transpose.FLIP_TOP_BOTTOM), rec))
        if a.both:
            cells.append((suffix_name(name, "_hv"), im.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.FLIP_TOP_BOTTOM), rec))
    place, size = pack(cells, pad=max(0, a.pad), columns=a.columns)
    bg = a.bg.lstrip("#")
    if len(bg) == 6: bg += "00"
    rgba = tuple(int(bg[i:i + 2], 16) for i in (0, 2, 4, 6))
    out = Image.new("RGBA", size, rgba)
    was_list = isinstance(data.get("frames"), list)
    new_hash, new_list = {}, []
    for name, im, rec in cells:
        x, y, im, rec = place[name]
        out.paste(im, (x, y), im)
        rewritten = rewrite(rec, x, y, im.width, im.height, filename=name if was_list else None)
        if was_list:
            rewritten.setdefault("filename", name); new_list.append(rewritten)
        else:
            new_hash[name] = rewritten
    data = json.loads(json.dumps(data))
    data["frames"] = new_list if was_list else new_hash
    meta = data.setdefault("meta", {})
    meta["size"] = {"w": out.width, "h": out.height}
    meta["image"] = os.path.basename(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    out.save(a.out)
    json.dump(data, open(atlas_out, "w"), indent=1)
    print(f"{len(cells)} frame(s), {out.width}x{out.height} -> {a.out} + {atlas_out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
