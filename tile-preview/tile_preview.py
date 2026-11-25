#!/usr/bin/env python3
"""tile-preview: render a Tiled JSON map (orthogonal) to a PNG without opening an editor: for review screenshots, PR
comments and CI artefacts. Tilesets are read from the map (embedded tilesets with an `image`, or --tileset PATH
to override the first one; external .tsx / .tsj tilesets are resolved next to the map). Tile flip flags (diagonal, horizontal, vertical) are applied
in Tiled's order. Optional: --objects draws object rectangles, points, ellipses and polygons with their names, --grid draws
the tile grid, --layers picks layers by name, --scale zooms with nearest-neighbour. Without a tileset image, tiles are drawn
as flat colours derived from their id. Hidden layers are skipped unless named in --layers.
"""
import argparse, os, json, sys
import colorsys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

H, V, D = 0x80000000, 0x40000000, 0x20000000


def tile_image(sheet, ts, lid, cache):
    if lid in cache: return cache[lid]
    tw, th, cols, m, sp = ts["tilewidth"], ts["tileheight"], ts.get("columns") or max(1, (sheet.width - 2 * ts.get("margin", 0) + ts.get("spacing", 0)) // (ts["tilewidth"] + ts.get("spacing", 0))), ts.get("margin", 0), ts.get("spacing", 0)
    x, y = m + (lid % cols) * (tw + sp), m + (lid // cols) * (th + sp)
    cache[lid] = sheet.crop((x, y, x + tw, y + th)); return cache[lid]


def flat(gid, tw, th):
    r, g, b = colorsys.hsv_to_rgb((gid * 0.618034) % 1, 0.55, 0.85); return Image.new("RGBA", (tw, th), (int(r * 255), int(g * 255), int(b * 255), 255))


def flip(img, gid):
    if gid & D: img = img.transpose(Image.TRANSPOSE)
    if gid & H: img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if gid & V: img = img.transpose(Image.FLIP_TOP_BOTTOM)
    return img


def render(m, tileset_png=None, base_dir=".", layers=None, objects=False, grid=False, scale=1):
    if m.get("orientation", "orthogonal") != "orthogonal": raise SystemExit("only orthogonal maps are supported")
    if m.get("infinite"): raise SystemExit("infinite maps (chunked layers) are not supported")
    m = map_diff.resolve_map_tilesets(map_diff.decode_map(m), base_dir)
    tw, th, W, Hh = m["tilewidth"], m["tileheight"], m["width"], m["height"]
    tss = sorted(m.get("tilesets", []), key=lambda t: t["firstgid"]); sheets = []
    if not tss and tileset_png: tss = [{"firstgid": 1, "tilewidth": tw, "tileheight": th}]                # maps without tileset entries (dungeon-gen output): use --tileset as tileset 1
    if not tss: tss = [{"firstgid": 1, "tilewidth": tw, "tileheight": th}]                                  # no tileset at all: flat colours per id
    for i, ts in enumerate(tss):
        path = tileset_png if (tileset_png and i == 0) else (ts["image"] if ts.get("image") else None)
        if path and not os.path.isabs(path) and not os.path.exists(path): path = os.path.join(base_dir, path)
        sheets.append(Image.open(path).convert("RGBA") if path and os.path.exists(path) else None)
    canvas = Image.new("RGBA", (W * tw, Hh * th), (0, 0, 0, 0)); cache = {}; drawn = 0

    def walk(ls):
        for l in ls:
            if l["type"] == "group": yield from walk(l["layers"])
            else: yield l
    for l in walk(m["layers"]):
        if layers is not None:
            if l["name"] not in layers: continue
        elif not l.get("visible", True): continue
        if l["type"] != "tilelayer": continue
        for i, g in enumerate(l.get("data") or map_diff.layer_gids(l)):
            gid = g & 0x0FFFFFFF
            if not gid: continue
            k = max((j for j, t in enumerate(tss) if t["firstgid"] <= gid), default=None)
            if k is None: continue
            ts = tss[k]; tile = tile_image(sheets[k], ts, gid - ts["firstgid"], cache.setdefault(k, {})) if sheets[k] else flat(gid, tw, th)
            tile = flip(tile, g)
            canvas.alpha_composite(tile.convert("RGBA"), ((i % W) * tw, (i // W) * th)); drawn += 1
    if grid:
        d = ImageDraw.Draw(canvas)
        for x in range(0, W * tw + 1, tw): d.line([(x, 0), (x, Hh * th)], fill=(255, 255, 255, 70))
        for y in range(0, Hh * th + 1, th): d.line([(0, y), (W * tw, y)], fill=(255, 255, 255, 70))
    if scale > 1: canvas = canvas.resize((canvas.width * scale, canvas.height * scale), Image.NEAREST)
    if objects:
        d = ImageDraw.Draw(canvas)
        for l in walk(m["layers"]):
            if l["type"] != "objectgroup" or (layers is not None and l["name"] not in layers) or (layers is None and not l.get("visible", True)): continue
            for o in l["objects"]:
                x, y, w, h = o["x"] * scale, o["y"] * scale, o.get("width", 0) * scale, o.get("height", 0) * scale
                col = (255, 60, 60, 255)
                if o.get("point"): d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=col, fill=col)
                elif o.get("polygon") or o.get("polyline"):
                    pts = [(x + p["x"] * scale, y + p["y"] * scale) for p in (o.get("polygon") or o.get("polyline"))]; d.line(pts + ([pts[0]] if o.get("polygon") else []), fill=col, width=2)
                elif o.get("ellipse"): d.ellipse([x, y, x + w, y + h], outline=col, width=2)
                else: d.rectangle([x, y, x + w, y + h], outline=col, width=2)
                if o.get("name"): d.text((x + 2, y + 2), o["name"], fill=(255, 255, 255, 255))
    return canvas, drawn


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a Tiled JSON map to PNG.")
    ap.add_argument("map"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--tileset"); ap.add_argument("--layers"); ap.add_argument("--objects", action="store_true")
    ap.add_argument("--grid", action="store_true"); ap.add_argument("--scale", type=int, default=1); ap.add_argument("--bg", help="background #rrggbb (default transparent)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); m = json.load(open(a.map))
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
    _src_keys = ('map',)
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

    img, n = render(m, a.tileset, os.path.dirname(os.path.abspath(a.map)), set(a.layers.split(",")) if a.layers else None, a.objects, a.grid, a.scale)
    if a.bg: s = a.bg.lstrip("#"); bg = Image.new("RGBA", img.size, tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)); bg.alpha_composite(img); img = bg
    if n == 0: print("WARN no tiles were drawn (all layers empty, hidden, or filtered out by --layers)")
    img.save(a.out); print(f"{n} tile(s) drawn, {img.width}x{img.height} -> {a.out}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
