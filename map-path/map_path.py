#!/usr/bin/env python3
"""map-path: find a walkable path on a finite orthogonal Tiled JSON map (A*).
Reuses map-reach's walkability rules (solid / ground layers and solid ids).
Writes a JSON report (and an optional PNG overlay). Exit 1 with --fail-if-none
when no path exists. The map is not rewritten; --json / --png may not overwrite
it unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, heapq, json, sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-reach"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import safe_out, map_reach, map_diff  # noqa: E402


def parse_xy(s):
    if not s:
        return None
    parts = s.replace(" ", "").split(",")
    if len(parts) != 2:
        raise SystemExit(f"expected X,Y, got {s!r}")
    return int(parts[0]), int(parts[1])


def astar(walk, start, goal, diagonal=False):
    h, w = walk.shape
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < w and 0 <= sy < h) or not walk[sy, sx]:
        raise SystemExit(f"start tile {start} is not a walkable cell")
    if not (0 <= gx < w and 0 <= gy < h) or not walk[gy, gx]:
        raise SystemExit(f"goal tile {goal} is not a walkable cell")
    steps = [(1, 0, 10), (-1, 0, 10), (0, 1, 10), (0, -1, 10)]
    if diagonal:
        steps += [(1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)]

    def heur(x, y):
        dx, dy = abs(x - gx), abs(y - gy)
        if diagonal:
            return 14 * min(dx, dy) + 10 * abs(dx - dy)
        return 10 * (dx + dy)

    openh = [(heur(sx, sy), 0, sx, sy)]
    came = {}
    gscore = {(sx, sy): 0}
    seen = set()
    while openh:
        _, g, x, y = heapq.heappop(openh)
        if (x, y) in seen:
            continue
        seen.add((x, y))
        if (x, y) == (gx, gy):
            path = [(x, y)]
            while (x, y) != (sx, sy):
                x, y = came[(x, y)]
                path.append((x, y))
            path.reverse()
            return path, g
        for dx, dy, cost in steps:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or not walk[ny, nx]:
                continue
            if dx and dy and not (walk[y, nx] and walk[ny, x]):
                continue
            ng = g + cost
            if ng < gscore.get((nx, ny), 1 << 30):
                gscore[(nx, ny)] = ng
                came[(nx, ny)] = (x, y)
                heapq.heappush(openh, (ng + heur(nx, ny), ng, nx, ny))
    return None, None


def render(walk, path, start, goal, scale=8):
    h, w = walk.shape
    im = Image.new("RGB", (w * scale, h * scale), (20, 20, 28))
    dr = ImageDraw.Draw(im)
    for y in range(h):
        for x in range(w):
            box = (x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1)
            if walk[y, x]:
                dr.rectangle(box, fill=(40, 80, 50))
            else:
                dr.rectangle(box, fill=(40, 30, 30))
    if path:
        pts = [(x * scale + scale // 2, y * scale + scale // 2) for x, y in path]
        if len(pts) >= 2:
            dr.line(pts, fill=(80, 200, 255), width=max(1, scale // 3))
        for x, y in path:
            r = max(1, scale // 4)
            cx, cy = x * scale + scale // 2, y * scale + scale // 2
            dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(80, 200, 255))
    for (x, y), col in ((start, (255, 220, 80)), (goal, (255, 80, 80))):
        box = (x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1)
        dr.rectangle(box, outline=col, width=max(1, scale // 6))
    return im


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A* path on a Tiled JSON map.")
    ap.add_argument("map")
    ap.add_argument("--start", help="start tile X,Y")
    ap.add_argument("--goal", help="goal tile X,Y")
    ap.add_argument("--start-name", default="spawn,start,player_start")
    ap.add_argument("--goal-name", default="goal,exit,end")
    ap.add_argument("--solid-layer")
    ap.add_argument("--ground-layer")
    ap.add_argument("--solid-ids", default="")
    ap.add_argument("--diagonal", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--png")
    ap.add_argument("--scale", type=int, default=8)
    ap.add_argument("--fail-if-none", action="store_true")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    for dest in (a.json, a.png):
        if dest:
            safe_out.check(a.map, dest, a.in_place)
    m = map_diff.decode_map(json.load(open(a.map, encoding="utf-8")))
    solid_ids = tuple(int(x) for x in a.solid_ids.split(",") if x.strip())
    walk = map_reach.walkable_grid(m, solid_layer=a.solid_layer, solid_ids=solid_ids,
                                   ground_layer=a.ground_layer)
    start = parse_xy(a.start)
    if start is None:
        start, _src = map_reach.find_start(m, a.start_name)
    goal = parse_xy(a.goal)
    if goal is None:
        goal, _src = map_reach.find_start(m, a.goal_name)
    if start is None:
        raise SystemExit("no start tile (pass --start or a spawn object)")
    if goal is None:
        raise SystemExit("no goal tile (pass --goal or a goal object)")
    path, cost = astar(walk, start, goal, diagonal=a.diagonal)
    rec = {
        "found": path is not None,
        "start": list(start),
        "goal": list(goal),
        "steps": (len(path) - 1) if path else None,
        "cost": cost,
        "path": [list(p) for p in path] if path else [],
        "diagonal": bool(a.diagonal),
    }
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    if a.png:
        os.makedirs(os.path.dirname(os.path.abspath(a.png)) or ".", exist_ok=True)
        render(walk, path, start, goal, scale=max(1, a.scale)).save(a.png)
    if path:
        print(f"path {start} -> {goal}, {rec['steps']} step(s), cost {cost}")
    else:
        print(f"no path {start} -> {goal}")
        if a.fail_if_none:
            return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
