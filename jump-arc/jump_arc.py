#!/usr/bin/env python3
"""jump-arc: preview a 2D jump / gravity arc over a Tiled map (or a blank canvas) and report range and apex.
Kinematic: x = x0 + vx t, y = y0 + vy t + 1/2 g t^2, with y down positive (Tiled space) or --y-up.
The arc is sampled until it hits a solid cell (non-empty tile on --solid-layer, or any non-empty cell)
or returns to the start height (blank canvas). Draws the polyline and apex on a tile-preview PNG (or a
blank frame). Multiple hops: --jumps N repeats the jump each time the arc lands.
"""
import argparse, os, json, math, sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-preview"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import tile_preview, map_diff  # noqa: E402

MASK = 0x1FFFFFFF


def solid_grid(m, layer_name):
    w, h = m["width"], m["height"]
    grid = [[False] * w for _ in range(h)]
    for name, l in map_diff.flat_layers(m.get("layers") or []):
        if l.get("type") != "tilelayer": continue
        if layer_name and name != layer_name and l.get("name") != layer_name: continue
        if layer_name is None and not l.get("visible", True): continue
        data = map_diff.layer_gids(l)
        lw = l.get("width") or w
        for i, g in enumerate(data):
            if g & MASK:
                x, y = i % lw, i // lw
                if 0 <= y < h and 0 <= x < w: grid[y][x] = True
        if layer_name: break
    return grid


def sample_arc(x0, y0, vx, vy, g, dt, max_t, solid, tw, th, y_up, jumps):
    """Return (points in pixels, apex, range, landed). y is in the same space as the map (down positive unless y_up)."""
    pts = [(x0, y0)]; t = 0.0
    apex = (x0, y0); hops = 0
    # convert: if y_up, gravity should accelerate toward -y? We keep an internal y-down by flipping.
    # User --y-up means input gravity is still "down" in magnitude; we flip screen y at the end? Easier:
    # store positions in pixel space with y down always. vy is given in "up is negative" if y_up? 
    # Convention: --jump-v is upward speed (positive), --gravity is downward magnitude (positive).
    sy = -1 if y_up else 1  # screen y grows down; upward velocity is -jump_v in screen space
    vx_s, vy_s, g_s = vx, -vy if True else vy, g  # always: vy input is upward, g is downward; screen y down
    # start
    x, y = x0, y0
    best_y = y  # smallest y is apex (up)
    landed = False
    oob = False
    hops_done = 0
    while t < max_t and hops_done < jumps:
        t += dt
        x = x0 + vx_s * t
        # after each landing we reset; easier to integrate hop by hop
        break
    # hop loop
    t_tot = 0.0
    while hops_done < jumps and t_tot < max_t:
        x, y = pts[-1]
        t = 0.0
        start_y = y
        oob = False
        while t < max_t - t_tot:
            t += dt
            xx = x + vx_s * t
            yy = y + vy_s * t + 0.5 * g_s * t * t
            pts.append((xx, yy))
            if yy < best_y: best_y = yy; apex = (xx, yy)
            # ground: back to start height of this hop (blank) or solid cell
            if solid is not None:
                cx, cy = int(xx // tw), int(yy // th)
                if 0 <= cy < len(solid) and 0 <= cx < len(solid[0]) and solid[cy][cx] and t > 2 * dt:
                    landed = True; oob = False; break
                if cy >= len(solid) or cx < 0 or cx >= (len(solid[0]) if solid else 0):
                    landed = True; oob = True; break
            else:
                if yy >= start_y and t > 2 * dt:
                    landed = True; break
        hops_done += 1
        t_tot += t
        # next hop starts at the landing point with a fresh upward vy
        # pts last is landing
    span = abs(pts[-1][0] - x0)
    return pts, apex, span, landed, oob


def main(argv=None):
    ap = argparse.ArgumentParser(description="Preview a jump / gravity arc over a Tiled map or a blank canvas.")
    ap.add_argument("map", nargs="?", help="Tiled JSON map (omit for a blank canvas)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--start", default="", help="pixel x,y (default: map left-centre, or canvas mid-left)")
    ap.add_argument("--jump-v", type=float, default=220, help="upward launch speed, px/s")
    ap.add_argument("--speed", type=float, default=120, help="horizontal speed, px/s")
    ap.add_argument("--gravity", type=float, default=800, help="downward gravity, px/s^2")
    ap.add_argument("--jumps", type=int, default=1); ap.add_argument("--dt", type=float, default=1 / 60)
    ap.add_argument("--max-s", type=float, default=8)
    ap.add_argument("--solid-layer", help="tile layer treated as solid (default: any non-empty visible tile)")
    ap.add_argument("--tileset"); ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--bg", default="202028"); ap.add_argument("--color", default="55ccff")
    ap.add_argument("--width", type=int, default=320); ap.add_argument("--height", type=int, default=180)
    ap.add_argument("--json")
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

    def col(s):
        s = s.lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    solid = m = None
    tw = th = 16
    if a.map:
        path = os.path.abspath(a.map); base = os.path.dirname(path)
        m = map_diff.resolve_map_tilesets(map_diff.decode_map(json.load(open(path))), base)
        tw, th = m["tilewidth"], m["tileheight"]
        solid = solid_grid(m, a.solid_layer)
        canvas, _ = tile_preview.render(m, a.tileset, base, scale=a.scale)
        if canvas.mode != "RGBA": canvas = canvas.convert("RGBA")
        bg = Image.new("RGBA", canvas.size, col(a.bg) + (255,)); bg.alpha_composite(canvas); canvas = bg
        x0, y0 = (tw * 2, m["height"] * th - th * 2) if not a.start else map(float, a.start.split(","))
        x0, y0 = x0 * a.scale, y0 * a.scale
        tw, th = tw * a.scale, th * a.scale
        # scale the solid grid? cell size is already tw,th scaled; grid is in tiles, we use tw,th
    else:
        canvas = Image.new("RGBA", (a.width, a.height), col(a.bg) + (255,))
        x0, y0 = (20, a.height - 20) if not a.start else map(float, a.start.split(","))
    pts, apex, span, landed, oob = sample_arc(x0, y0, a.speed, a.jump_v, a.gravity, a.dt, a.max_s, solid, tw, th, False, a.jumps)
    # scale points if map scale already applied to start and tw
    dr = ImageDraw.Draw(canvas)
    xy = [(p[0], p[1]) for p in pts]
    if len(xy) >= 2: dr.line(xy, fill=col(a.color) + (255,), width=max(1, a.scale))
    ax, ay = apex
    r = 3 * max(1, a.scale)
    dr.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(255, 220, 80, 255))
    dr.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=(255, 80, 80, 255))
    canvas.save(a.out)
    rec = {"points": len(pts), "apex": [round(ax, 1), round(ay, 1)], "range_px": round(span, 1),
           "landed": landed, "out_of_bounds": oob, "start": [x0, y0],
           "end": [round(pts[-1][0], 1), round(pts[-1][1], 1)], "jumps": a.jumps}
    print(f"{len(pts)} sample(s), range {rec['range_px']} px, apex ({ax:.1f}, {ay:.1f}), landed={landed} -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
