#!/usr/bin/env python3
"""wfc-tiles: overlapping-free "simple tiled" Wave Function Collapse for level layouts.

Learns adjacency rules from a small example grid (CSV of tile ids, or a PNG where each pixel colour
is a tile) and generates new grids of any size that only use observed neighbour pairs.
Clean-room implementation of the idea popularised by mxgmn/WaveFunctionCollapse (MIT).
"""
import argparse, csv, json, os, random, sys
from collections import defaultdict
from PIL import Image
import os, sys

DIRS = [(0, -1, 0), (1, 0, 1), (0, 1, 2), (-1, 0, 3)]  # dx, dy, idx (N,E,S,W)
OPP = [2, 3, 0, 1]


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def learn(grid, wrap=False):
    h, w = len(grid), len(grid[0])
    tiles = sorted({t for row in grid for t in row})
    weights = defaultdict(int)
    rules = {t: [set() for _ in range(4)] for t in tiles}
    for y in range(h):
        for x in range(w):
            t = grid[y][x]
            weights[t] += 1
            for dx, dy, d in DIRS:
                nx, ny = x + dx, y + dy
                if wrap:
                    nx, ny = nx % w, ny % h
                elif not (0 <= nx < w and 0 <= ny < h):
                    continue
                rules[t][d].add(grid[ny][nx])
    return tiles, dict(weights), rules


class Contradiction(Exception):
    pass


def generate(tiles, weights, rules, w, h, seed=None, max_tries=50):
    rnd = random.Random(seed)
    for _ in range(max_tries):
        try:
            return _run(tiles, weights, rules, w, h, rnd)
        except Contradiction:
            continue
    raise RuntimeError("WFC failed after retries; try another seed or a richer example")


def _run(tiles, weights, rules, w, h, rnd):
    wave = [[set(tiles) for _ in range(w)] for _ in range(h)]
    import math
    while True:
        best, best_e = None, None
        for y in range(h):
            for x in range(w):
                opts = wave[y][x]
                if len(opts) == 0:
                    raise Contradiction
                if len(opts) > 1:
                    tw = sum(weights[t] for t in opts)
                    e = math.log(tw) - sum(weights[t] * math.log(weights[t]) for t in opts) / tw
                    e += rnd.random() * 1e-6
                    if best_e is None or e < best_e:
                        best, best_e = (x, y), e
        if best is None:
            return [[next(iter(wave[y][x])) for x in range(w)] for y in range(h)]
        x, y = best
        opts = sorted(wave[y][x])
        pick = rnd.choices(opts, weights=[weights[t] for t in opts])[0]
        wave[y][x] = {pick}
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            for dx, dy, d in DIRS:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                allowed = set()
                for t in wave[cy][cx]:
                    allowed |= rules[t][d]
                new = wave[ny][nx] & allowed
                if new != wave[ny][nx]:
                    if not new:
                        raise Contradiction
                    wave[ny][nx] = new
                    stack.append((nx, ny))


def valid(grid, rules):
    h, w = len(grid), len(grid[0])
    for y in range(h):
        for x in range(w):
            for dx, dy, d in DIRS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] not in rules[grid[y][x]][d]:
                    return False
    return True


def read_example(path):
    low = path.lower()
    if low.endswith(".png") or low.endswith(".gif"):
        im = Image.open(path).convert("RGB")
        px = im.load()
        grid = [["%02x%02x%02x" % px[x, y] for x in range(im.width)] for y in range(im.height)]
        kind = "png"
    elif low.endswith((".json", ".tmj")):
        data = gst_read.require_object(gst_read.load_json(path, "Tiled map"), "Tiled map")
        layers = data.get("layers") or []
        layer = next((l for l in layers if isinstance(l, dict) and l.get("type") in (None, "tilelayer") and "data" in l), None)
        if layer is None:
            raise GstInputError("Tiled map has no tile layer")
        w, h = int(layer.get("width") or data.get("width") or 0), int(layer.get("height") or data.get("height") or 0)
        gids = layer.get("data") or []
        if isinstance(gids, str):
            raise GstInputError("Tiled layer data is encoded; use a CSV example or a decoded JSON map")
        if not isinstance(gids, list) or w < 1 or h < 1:
            raise GstInputError("WFC example is empty")
        gst_read.check_tiled_layer_length(gids, w, h, layer.get("name") or "")
        grid = [[str(gids[y * w + x]) for x in range(w)] for y in range(h)]
        kind = "csv"
    else:
        with open(path, encoding="utf-8") as f:
            grid = [[c.strip() for c in row] for row in csv.reader(f) if row]
        kind = "csv"
    if not grid or not grid[0]:
        raise GstInputError("WFC example is empty")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise GstInputError("WFC example rows have uneven length")
    return grid, kind


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate tile maps with Wave Function Collapse.")
    ap.add_argument("example", help="example CSV of tile ids or PNG (1 px = 1 tile)")
    ap.add_argument("-o", "--out", required=True, help=".csv, .png, or .json (Tiled-style)")
    ap.add_argument("--size", default="32x18")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--wrap", action="store_true", help="treat the example as tileable")
    ap.add_argument("--scale", type=int, default=1, help="PNG output upscale")
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
    _src_keys = ('example',)
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

    grid, kind = read_example(a.example)
    tiles, weights, rules = learn(grid, a.wrap)
    w, h = (int(v) for v in a.size.lower().split("x"))
    out = generate(tiles, weights, rules, w, h, a.seed)
    ext = os.path.splitext(a.out)[1].lower()
    if ext == ".png":
        im = Image.new("RGB", (w, h))
        for y in range(h):
            for x in range(w):
                t = out[y][x]
                im.putpixel((x, y), tuple(int(t[i:i + 2], 16) for i in (0, 2, 4)) if kind == "png" else (hash(t) & 0xFF, (hash(t) >> 8) & 0xFF, (hash(t) >> 16) & 0xFF))
        if a.scale > 1:
            im = im.resize((w * a.scale, h * a.scale), Image.Resampling.NEAREST)
        im.save(a.out)
    elif ext == ".json":
        ids = {t: i + 1 for i, t in enumerate(tiles)}
        json.dump({"width": w, "height": h, "tilewidth": 16, "tileheight": 16, "orientation": "orthogonal",
                   "type": "map", "infinite": False,
                   "layers": [{"name": "wfc", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
                               "opacity": 1, "visible": True, "data": [ids[t] for row in out for t in row]}],
                   "properties": [{"name": "tile_ids", "type": "string", "value": json.dumps(ids)}]},
                  open(a.out, "w"), indent=1)
    else:
        with open(a.out, "w", newline="") as f:
            csv.writer(f).writerows(out)
    print(f"generated {w}x{h} map from {len(tiles)} tiles -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
