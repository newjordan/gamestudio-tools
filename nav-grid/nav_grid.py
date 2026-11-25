#!/usr/bin/env python3
"""nav-grid: render a walkability grid (and optional BFS distance field) from a Tiled tile
layer. Reuses map-reach's `walkable_grid` / flood rules (`--solid-layer`, `--solid-ids`,
`--ground-layer`, `--diagonal`). Encoded tile data is decoded first. Writes a PNG and
optionally a distance CSV; the input map is never overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys
from collections import deque

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-reach"))
import safe_out, map_diff, map_reach  # noqa: E402


def distances(walk, start, diagonal=False):
    """BFS distances from start. Unreached / blocked cells are -1."""
    h, w = walk.shape
    dist = np.full((h, w), -1, dtype=np.int32)
    sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h) or not walk[sy, sx]:
        raise SystemExit(f"start tile {start} is not a walkable cell")
    q = deque([(sx, sy)])
    dist[sy, sx] = 0
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diagonal else [])
    while q:
        x, y = q.popleft()
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and walk[ny, nx] and dist[ny, nx] < 0:
                if dx and dy and not (walk[y, nx] and walk[ny, x]):
                    continue
                dist[ny, nx] = dist[y, x] + 1
                q.append((nx, ny))
    return dist


def render(walk, dist=None, start=None, scale=8):
    h, w = walk.shape
    # solid: #1a1a1a, walkable unreached: #3d5a3d, reached: heat from #d8f0d8 to #2a6a2a, start: #ffcc33
    img = Image.new("RGB", (w, h), (26, 26, 26))
    px = img.load()
    maxd = int(dist.max()) if dist is not None and (dist >= 0).any() else 0
    for y in range(h):
        for x in range(w):
            if not walk[y, x]:
                continue
            if dist is None or dist[y, x] < 0:
                px[x, y] = (61, 90, 61)
            else:
                t = 0 if maxd == 0 else dist[y, x] / maxd
                # close = light, far = dark green
                r = int(216 + (42 - 216) * t)
                g = int(240 + (106 - 240) * t)
                b = int(216 + (42 - 216) * t)
                px[x, y] = (r, g, b)
    if start is not None:
        sx, sy = start
        if 0 <= sx < w and 0 <= sy < h:
            px[sx, sy] = (255, 204, 51)
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    return img


def parse_start(s):
    if not s:
        return None
    parts = s.split(",")
    if len(parts) != 2:
        raise SystemExit("--start must be X,Y tile coordinates")
    return int(parts[0]), int(parts[1])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a walkability grid / BFS distance field from a Tiled map.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True, help="output PNG")
    ap.add_argument("--solid-layer", help="tile layer whose non-zero cells are blocked")
    ap.add_argument("--ground-layer", help="tile layer whose zero cells are blocked")
    ap.add_argument("--solid-ids", help="comma-separated tile IDs (firstgid + local) treated as blocked")
    ap.add_argument("--start", help="X,Y tile coordinate to flood from (optional)")
    ap.add_argument("--start-name", default="spawn,start,player_start",
                    help="object name(s) used when --start is omitted and a start object exists")
    ap.add_argument("--diagonal", action="store_true")
    ap.add_argument("--scale", type=int, default=8)
    ap.add_argument("--dist-csv", help="write a CSV of BFS distances (-1 = blocked or unreached)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    safe_out.check(a.map, a.dist_csv, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    raw = json.load(open(a.map, encoding="utf-8"))
    m = map_diff.decode_map(raw)
    if a.solid_ids:
        solid_ids = tuple(int(x) for x in a.solid_ids.split(",") if x.strip())
    else:
        solid_ids = ()
    walk = map_reach.walkable_grid(m, solid_layer=a.solid_layer, solid_ids=solid_ids, ground_layer=a.ground_layer)
    start = parse_start(a.start)
    if start is None:
        start, _src = map_reach.find_start(m, a.start_name)
    dist = distances(walk, start, a.diagonal) if start is not None else None
    if a.scale < 1:
        sys.exit("--scale must be >= 1")
    img = render(walk, dist, start, a.scale)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    img.save(a.out)
    if a.dist_csv:
        if dist is None:
            sys.exit("--dist-csv requires a start tile (--start or a start object)")
        os.makedirs(os.path.dirname(os.path.abspath(a.dist_csv)) or ".", exist_ok=True)
        with open(a.dist_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for row in dist.tolist():
                w.writerow(row)
    rec = {"width": int(walk.shape[1]), "height": int(walk.shape[0]),
           "walkable": int(walk.sum()), "start": list(start) if start else None,
           "reachable": int((dist >= 0).sum()) if dist is not None else None,
           "max_dist": int(dist.max()) if dist is not None and (dist >= 0).any() else None,
           "out": a.out}
    print(f"{rec['walkable']} walkable tile(s)" +
          (f", start {start}, reach {rec['reachable']}, max dist {rec['max_dist']}" if start else "") +
          f" -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
