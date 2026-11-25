#!/usr/bin/env python3
"""tmx-layer-export: export each tile layer of a Tiled JSON map as a PNG (via tile-preview), plus a stacked composite.
Layer PNGs are named with a 2-digit index and a flattened path (groups use __). Hidden layers are skipped unless
--include-hidden. Encoded tile data is decoded and external .tsx / .tsj tilesets are resolved (same helpers as
tile-preview). --scale is nearest-neighbour; --bg paints an opaque backdrop; --objects draws object layers on the
composite only.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-preview"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import tile_preview, map_diff  # noqa: E402


def flat_tile_layers(layers, prefix=""):
    for l in layers or []:
        name = prefix + l.get("name", "")
        if l.get("type") == "group":
            yield from flat_tile_layers(l.get("layers") or [], name + "/")
        elif l.get("type") == "tilelayer":
            yield name, l


def safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name.replace("/", "__")) or "layer"


def paint_bg(img, bg):
    if not bg: return img
    s = bg.lstrip("#"); rgba = tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    out = Image.new("RGBA", img.size, rgba); out.alpha_composite(img); return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export each Tiled tile layer (and a composite) as a PNG.")
    ap.add_argument("map"); ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--tileset"); ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--bg", help="background #rrggbb (default transparent)")
    ap.add_argument("--include-hidden", action="store_true")
    ap.add_argument("--no-composite", action="store_true")
    ap.add_argument("--objects", action="store_true", help="draw object layers on the composite")
    ap.add_argument("--grid", action="store_true")
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

    path = os.path.abspath(a.map); base = os.path.dirname(path)
    m = map_diff.resolve_map_tilesets(map_diff.decode_map(json.load(open(path))), base)
    os.makedirs(a.outdir, exist_ok=True)
    layers = [(n, l) for n, l in flat_tile_layers(m.get("layers") or []) if a.include_hidden or l.get("visible", True)]
    written = []
    for i, (name, l) in enumerate(layers, 1):
        mm = dict(m); mm["layers"] = [l]
        img, n = tile_preview.render(mm, a.tileset, base, layers=None, objects=False, grid=a.grid, scale=a.scale)
        img = paint_bg(img, a.bg)
        dest = os.path.join(a.outdir, f"{i:02d}_{safe(name)}.png"); img.save(dest)
        print(f"{name}: {n} tile(s) -> {dest}"); written.append(dest)
    if not a.no_composite:
        img, n = tile_preview.render(m, a.tileset, base, layers=None, objects=a.objects, grid=a.grid, scale=a.scale)
        img = paint_bg(img, a.bg)
        dest = os.path.join(a.outdir, "composite.png"); img.save(dest)
        print(f"composite: {n} tile(s) -> {dest}"); written.append(dest)
    if not written: print("no tile layers to export")
    return 0 if written else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
