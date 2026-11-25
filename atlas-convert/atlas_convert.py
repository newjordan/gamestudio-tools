#!/usr/bin/env python3
"""atlas-convert: convert the atlas JSON written by atlas-pack (TexturePacker "hash" layout) to other formats:
  array     TexturePacker "array" JSON (Phaser/Pixi accept both)
  libgdx    libGDX TextureAtlas text (.atlas)        (offset y measured from the bottom, as libGDX expects)
  starling  Starling/Sparrow XML (.xml)              (frameX/frameY are negative trim offsets)
  css       CSS sprite classes (.css)
  hash      array -> hash (back again)
Frames are never rotated by atlas-pack, so `rotate` is always false. Trim metadata (spriteSourceSize/sourceSize)
is carried through. Formats follow the public libGDX and Starling file-format docs.
"""
import argparse, json, os
import os, sys


def frames_of(meta):
    f = meta["frames"]
    if isinstance(f, dict):
        return [{"filename": k, **v} for k, v in f.items()]
    return [dict(x) for x in f]


def src_of(fr):
    s = fr.get("spriteSourceSize") or {"x": 0, "y": 0, "w": fr["frame"]["w"], "h": fr["frame"]["h"]}
    o = fr.get("sourceSize") or {"w": fr["frame"]["w"], "h": fr["frame"]["h"]}
    return s, o


def to_array(meta):
    return {"frames": [{"filename": f["filename"], **{k: v for k, v in f.items() if k != "filename"}} for f in frames_of(meta)], "meta": meta["meta"]}


def to_hash(meta):
    return {"frames": {f["filename"]: {k: v for k, v in f.items() if k != "filename"} for f in frames_of(meta)}, "meta": meta["meta"]}


def to_libgdx(meta, image=None):
    m = meta["meta"]; image = image or m["image"]
    L = ["", image, f"size: {m['size']['w']}, {m['size']['h']}", "format: RGBA8888", "filter: Nearest, Nearest", "repeat: none"]
    for f in frames_of(meta):
        r = f["frame"]; s, o = src_of(f)
        L += [f["filename"], "  rotate: false", f"  xy: {r['x']}, {r['y']}", f"  size: {r['w']}, {r['h']}",
              f"  orig: {o['w']}, {o['h']}", f"  offset: {s['x']}, {o['h'] - r['h'] - s['y']}", "  index: -1"]
    return "\n".join(L) + "\n"


def to_starling(meta, image=None):
    m = meta["meta"]; image = image or m["image"]
    L = [f'<TextureAtlas imagePath="{image}">']
    for f in frames_of(meta):
        r = f["frame"]; s, o = src_of(f)
        extra = f' frameX="{-s["x"]}" frameY="{-s["y"]}" frameWidth="{o["w"]}" frameHeight="{o["h"]}"' if (s["x"] or s["y"] or (o["w"], o["h"]) != (r["w"], r["h"])) else ""
        L.append(f'  <SubTexture name="{f["filename"]}" x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}"{extra}/>')
    return "\n".join(L + ["</TextureAtlas>"]) + "\n"


def to_css(meta, image=None, prefix="spr-"):
    m = meta["meta"]; image = image or m["image"]
    L = [f".{prefix}atlas {{ background-image: url('{image}'); background-repeat: no-repeat; image-rendering: pixelated; display: inline-block; }}"]
    for f in frames_of(meta):
        r = f["frame"]; name = "".join(c if c.isalnum() or c in "-_" else "-" for c in f["filename"])
        L.append(f".{prefix}{name} {{ width: {r['w']}px; height: {r['h']}px; background-position: -{r['x']}px -{r['y']}px; }}")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert atlas JSON to other engine formats.")
    ap.add_argument("json"); ap.add_argument("--to", choices=["array", "hash", "libgdx", "starling", "css"], required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--image", help="image name to write in the output (default: from meta)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if getattr(a, 'out', None) and os.path.abspath(a.out) == os.path.abspath(a.json) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    meta = json.load(open(a.json))
    if a.to in ("array", "hash"):
        json.dump(to_array(meta) if a.to == "array" else to_hash(meta), open(a.out, "w"), indent=2)
    else:
        txt = {"libgdx": to_libgdx, "starling": to_starling, "css": to_css}[a.to](meta, a.image)
        open(a.out, "w", encoding="utf-8").write(txt)
    print(f"wrote {a.out} ({a.to}, {len(frames_of(meta))} frames)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
