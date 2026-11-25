#!/usr/bin/env python3
"""tile-anim-gif: render Tiled animated tiles to GIFs, for reviewing water, torches, conveyors and the like.
Reads a Tiled tileset JSON (or a map with an embedded tileset that has tiles[].animation = [{tileid, duration}, ...])
plus the tileset image, and writes one GIF per animated tile (durations honoured, looped). With --map, also writes a
preview GIF of the whole map with those animations playing (finite orthogonal maps, via tile-preview; flip flags are
kept). --scale is nearest-neighbour. Tiles without an animation are skipped. External .tsx / .tsj tilesets (a map's `source`, or a .tsx file as INPUT) are resolved next to the tileset file.
"""
import argparse, os, json, sys
from math import gcd
from functools import reduce

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tile-preview"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import tile_preview, map_diff  # noqa: E402

MASK = 0x1FFFFFFF
FLAGS = 0xE0000000


def lcm(a, b): return a * b // gcd(a, b) if a and b else a or b


def load_tilesets(data, base, image_override=None):
    """Yield (firstgid, tilewidth, tileheight, image_path, tiles_by_local_id) for each tileset that has an image."""
    if data.get("type") == "map": sets = data.get("tilesets") or []
    else: sets = [data] if data.get("image") or data.get("tiles") or data.get("source") or data.get("tilewidth") else data.get("tilesets") or [data]
    out = []
    for ts in sets:
        ts = map_diff.resolve_tileset(ts, base)
        img = image_override or ts.get("image")
        if not img: continue
        if image_override and os.path.isfile(image_override): path = image_override
        else: path = img if os.path.isabs(img) else os.path.join(base, img)
        if not os.path.isfile(path): raise SystemExit(f"tileset image not found: {path}")
        tiles = {int(t["id"]): t for t in (ts.get("tiles") or []) if "id" in t}
        out.append({"firstgid": ts.get("firstgid", 1), "tw": ts.get("tilewidth") or data.get("tilewidth"),
                    "th": ts.get("tileheight") or data.get("tileheight"), "columns": ts.get("columns"),
                    "image": path, "tiles": tiles, "name": ts.get("name") or os.path.splitext(os.path.basename(path))[0]})
    return out


def tile_image(sheet, tw, th, columns, local_id):
    cols = columns or max(1, sheet.width // tw)
    x, y = (local_id % cols) * tw, (local_id // cols) * th
    return sheet.crop((x, y, x + tw, y + th))


def animations_of(ts):
    out = {}
    for lid, t in ts["tiles"].items():
        anim = t.get("animation") or []
        if anim: out[lid] = [(int(f["tileid"]), int(f["duration"])) for f in anim]
    return out


def gif_from_anim(sheet, ts, frames, scale, dest):
    ims, durs = [], []
    for lid, ms in frames:
        im = tile_image(sheet, ts["tw"], ts["th"], ts["columns"], lid)
        if scale != 1: im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        ims.append(im.convert("RGB")); durs.append(max(1, ms))
    ims[0].save(dest, save_all=True, append_images=ims[1:], duration=durs, loop=0, dispose=2)
    return dest, sum(durs)


def remap_map(m, ts_anims, time_ms):
    """Return a copy of m whose animated gids have been swapped to the frame at time_ms (flags kept)."""
    m = map_diff.decode_map(m)
    # table: global gid (unflagged) -> replacement local+firstgid
    table = {}
    for ts, anims in ts_anims:
        fg = ts["firstgid"]
        for lid, frames in anims.items():
            total = sum(d for _, d in frames) or 1; t = time_ms % total; acc = 0; pick = frames[-1][0]
            for tid, d in frames:
                acc += d
                if t < acc: pick = tid; break
            table[fg + lid] = fg + pick
    def remap_list(data):
        out = []
        for g in data:
            gid, flags = g & MASK, g & FLAGS
            out.append((table.get(gid, gid) | flags) if gid else 0)
        return out
    def walk(layers):
        for l in layers:
            if l.get("type") == "group": walk(l.get("layers") or [])
            elif l.get("type") == "tilelayer":
                if "chunks" in l:
                    for c in l["chunks"]: c["data"] = remap_list(c.get("data") or [])
                elif isinstance(l.get("data"), list): l["data"] = remap_list(l["data"])
    walk(m.get("layers") or []); return m


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render Tiled animated tiles (and optional maps) to GIFs.")
    ap.add_argument("input", help="Tiled map JSON or tileset JSON"); ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--image", help="tileset PNG (default: the tileset's image, next to the JSON)")
    ap.add_argument("--map", help="also write a map preview GIF (if INPUT is already a map, this can be omitted and is implied)")
    ap.add_argument("--scale", type=int, default=1); ap.add_argument("--tick-ms", type=int, default=50, help="map GIF frame step")
    ap.add_argument("--duration-ms", type=int, help="map GIF length (default: LCM of animation cycles, capped at 8s)")
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
    _src_keys = ('input', 'image', 'map')
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

    inp = os.path.abspath(a.input); base = os.path.dirname(inp)
    if inp.lower().endswith((".tsx", ".xml")): data = map_diff.load_tsx(inp)
    else: data = json.load(open(inp)); data = map_diff.decode_map(data) if data.get("type") == "map" else data
    sets = load_tilesets(data, base, a.image)
    if not sets: sys.exit("no tileset image found (embed the tileset or pass --image)")
    os.makedirs(a.outdir, exist_ok=True)
    ts_anims, written = [], 0
    for ts in sets:
        sheet = Image.open(ts["image"]).convert("RGBA"); anims = animations_of(ts); ts_anims.append((ts, anims))
        for lid, frames in anims.items():
            dest = os.path.join(a.outdir, f"{ts['name']}_{lid}.gif")
            _, total = gif_from_anim(sheet, ts, frames, a.scale, dest)
            print(f"tile {ts['name']} #{lid}: {len(frames)} frame(s), {total} ms -> {dest}"); written += 1
    if not written: print("no animated tiles found")
    want_map = a.map or (data.get("type") == "map")
    map_path, map_data = (a.map, map_diff.decode_map(json.load(open(a.map)))) if a.map else ((a.input, data) if data.get("type") == "map" else (None, None))
    if want_map and map_data is not None:
        cycles = [sum(d for _, d in frames) for _, anims in ts_anims for frames in anims.values()]
        period = reduce(lcm, cycles, 1) if cycles else a.tick_ms
        length = a.duration_ms or min(period, 8000)
        tick = max(1, a.tick_ms); n = max(1, int(round(length / tick)))
        frames = []
        for i in range(n):
            mm = remap_map(map_data, ts_anims, i * tick)
            im, _ = tile_preview.render(mm, a.image, os.path.dirname(os.path.abspath(map_path)), scale=a.scale)
            frames.append(im.convert("RGB"))
        dest = os.path.join(a.outdir, "map.gif")
        if frames: frames[0].save(dest, save_all=True, append_images=frames[1:], duration=tick, loop=0); print(f"map preview: {n} frame(s) x {tick} ms -> {dest}")
    return 0 if written or (want_map and map_data is not None) else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
