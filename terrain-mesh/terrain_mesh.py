#!/usr/bin/env python3
"""terrain-mesh: heightmap PNG (8-bit or 16-bit greyscale) -> GLB terrain mesh, optionally split into a grid of
chunks (for streaming / culling). Smooth normals from the height field, UVs 0..1 across the whole terrain,
--step to subsample dense maps, --scale X,Y,Z for world size (Y = height range). Pairs with terrain-noise.
Chunks overlap by one vertex row/column so their edges meet without cracks.
"""
import argparse, json, os, struct
import numpy as np
from PIL import Image
import os, sys


def load_height(path):
    im = Image.open(path)
    a = np.array(im)
    if a.ndim == 3: a = np.array(im.convert("L"))
    a = a.astype(np.float64)
    return a / (65535.0 if a.max() > 255 else 255.0)


def normals(h, sx, sz, sy):
    gz, gx = np.gradient(h * sy, sz / max(h.shape[0] - 1, 1), sx / max(h.shape[1] - 1, 1))
    n = np.stack([-gx, np.ones_like(h), -gz], -1)
    return (n / np.linalg.norm(n, axis=-1, keepdims=True)).astype(np.float32)


def mesh_arrays(h, scale, step, region=None):
    sx, sy, sz = scale
    H, W = h.shape
    nfull = normals(h, sx, sz, sy)
    y0, y1, x0, x1 = region or (0, H, 0, W)
    ys = np.arange(y0, y1, step); xs = np.arange(x0, x1, step)
    if ys[-1] != y1 - 1: ys = np.append(ys, y1 - 1)
    if xs[-1] != x1 - 1: xs = np.append(xs, x1 - 1)
    gy, gx = np.meshgrid(ys, xs, indexing="ij")
    pos = np.stack([gx / (W - 1) * sx, h[gy, gx] * sy, gy / (H - 1) * sz], -1).reshape(-1, 3).astype(np.float32)
    nor = nfull[gy, gx].reshape(-1, 3)
    uv = np.stack([gx / (W - 1), gy / (H - 1)], -1).reshape(-1, 2).astype(np.float32)
    ny, nx = gy.shape; idx = []
    ii = np.arange(ny * nx).reshape(ny, nx)
    a, b, c, d = ii[:-1, :-1], ii[:-1, 1:], ii[1:, :-1], ii[1:, 1:]
    idx = np.stack([a, c, b, b, c, d], -1).reshape(-1).astype(np.uint32)
    return pos, nor, uv, idx


def write_glb(path, pos, nor, uv, idx, name="terrain"):
    parts, views, off = [], [], 0
    def add(data, tgt):
        nonlocal off
        pad = -off % 4; parts.append(b"\0" * pad); off += pad
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": tgt}); parts.append(data); off += len(data); return len(views) - 1
    big = len(pos) >= 65536
    accs = [{"bufferView": add(pos.tobytes(), 34962), "componentType": 5126, "count": len(pos), "type": "VEC3", "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
            {"bufferView": add(nor.tobytes(), 34962), "componentType": 5126, "count": len(pos), "type": "VEC3"},
            {"bufferView": add(uv.tobytes(), 34962), "componentType": 5126, "count": len(pos), "type": "VEC2"},
            {"bufferView": add(idx.astype("<u4" if big else "<u2").tobytes(), 34963), "componentType": 5125 if big else 5123, "count": len(idx), "type": "SCALAR"}]
    g = {"asset": {"version": "2.0", "generator": "gamestudio-tools terrain-mesh"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3}]}], "accessors": accs, "bufferViews": views}
    bin_ = b"".join(parts); bin_ += b"\0" * (-len(bin_) % 4); g["buffers"] = [{"byteLength": len(bin_)}]
    js = json.dumps(g, separators=(",", ":")).encode(); js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_))); f.write(struct.pack("<I4s", len(js), b"JSON") + js); f.write(struct.pack("<I4s", len(bin_), b"BIN\x00") + bin_)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Heightmap PNG to GLB terrain.")
    ap.add_argument("heightmap"); ap.add_argument("-o", "--out", required=True, help="output .glb (chunks get _cX_Y suffixes)")
    ap.add_argument("--scale", default="100,20,100", help="world size X,Y(height),Z")
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--chunks", type=int, default=1, help="split into NxN files")
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
    _src_keys = ('heightmap',)
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

    h = load_height(a.heightmap); sc = tuple(float(v) for v in a.scale.split(","))
    H, W = h.shape; n = a.chunks
    for cy in range(n):
        for cx in range(n):
            reg = None if n == 1 else (cy * (H - 1) // n, (cy + 1) * (H - 1) // n + 1, cx * (W - 1) // n, (cx + 1) * (W - 1) // n + 1)
            pos, nor, uv, idx = mesh_arrays(h, sc, a.step, reg)
            out = a.out if n == 1 else f"{os.path.splitext(a.out)[0]}_c{cx}_{cy}.glb"
            write_glb(out, pos, nor, uv, idx, os.path.splitext(os.path.basename(out))[0])
            print(f"{out}: {len(pos)} verts, {len(idx) // 3} tris")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
