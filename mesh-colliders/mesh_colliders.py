#!/usr/bin/env python3
"""mesh-colliders: derive simple collision primitives from a .glb: world-space AABB, oriented box (PCA),
bounding sphere and a vertical capsule, per mesh node and for the whole file. Output JSON includes the
engine-ready numbers (Godot BoxShape3D size / SphereShape3D radius / CapsuleShape3D radius+height, and
centre transforms). Node TRS/matrix transforms are applied; skinned meshes use the bind pose.
The oriented box uses principal axes of the vertex cloud (good for elongated props); the sphere is
Ritter's approximate bounding sphere (a few % larger than minimal).
"""
import os
import argparse, json, struct, sys
import numpy as np

NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
DT = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def load_glb(path):
    return gst_read.load_glb(path)


def read_positions(g, b, idx):
    a = g["accessors"][idx]; bv = g["bufferViews"][a["bufferView"]]
    dt = np.dtype("<" + DT[a["componentType"]]); n = NC[a["type"]]
    stride = bv.get("byteStride") or n * dt.itemsize; off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    buf = np.frombuffer(b, np.uint8)
    raw = np.lib.stride_tricks.as_strided(buf[off:], shape=(a["count"], n * dt.itemsize), strides=(stride, 1))
    arr = np.ascontiguousarray(raw).view(dt).reshape(a["count"], n).astype(np.float64)
    if a.get("normalized"): arr = arr / np.iinfo(dt).max
    return arr


def node_matrix(n):
    if "matrix" in n: return np.array(n["matrix"], np.float64).reshape(4, 4).T
    t = np.array(n.get("translation", [0, 0, 0]), np.float64); q = n.get("rotation", [0, 0, 0, 1]); s = n.get("scale", [1, 1, 1])
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * np.array(s); M[:3, 3] = t
    return M


def world_vertices(g, b):
    out = []
    def walk(i, parent):
        n = g["nodes"][i]; M = parent @ node_matrix(n)
        if "mesh" in n:
            pts = [read_positions(g, b, p["attributes"]["POSITION"]) for p in g["meshes"][n["mesh"]]["primitives"]]
            v = np.concatenate(pts); v = (np.c_[v, np.ones(len(v))] @ M.T)[:, :3]
            out.append((n.get("name", f"node_{i}"), v))
        for c in n.get("children", []): walk(c, M)
    scene = g["scenes"][g.get("scene", 0)]
    for r in scene["nodes"]: walk(r, np.eye(4))
    return out


def shapes(v):
    mn, mx = v.min(0), v.max(0)
    aabb = {"center": ((mn + mx) / 2).tolist(), "size": (mx - mn).tolist()}
    c = v.mean(0); u, s, vt = np.linalg.svd(v - c, full_matrices=False) if len(v) > 3 else (None, None, np.eye(3))
    ax = vt if np.linalg.det(vt) > 0 else vt * np.array([[1], [1], [-1]])
    loc = (v - c) @ ax.T; lmn, lmx = loc.min(0), loc.max(0)
    obb = {"center": (c + ((lmn + lmx) / 2) @ ax).tolist(), "size": (lmx - lmn).tolist(), "axes": ax.tolist()}
    p0 = v[0]; p1 = v[np.argmax(np.linalg.norm(v - p0, axis=1))]; p2 = v[np.argmax(np.linalg.norm(v - p1, axis=1))]
    ctr = (p1 + p2) / 2; r = np.linalg.norm(p1 - p2) / 2
    for p in v:
        d = np.linalg.norm(p - ctr)
        if d > r: r = (r + d) / 2; ctr = ctr + (p - ctr) * ((d - r) / d)
    sphere = {"center": ctr.tolist(), "radius": float(r)}
    rad = float(max(mx[0] - mn[0], mx[2] - mn[2]) / 2); h = float(mx[1] - mn[1])
    capsule = {"center": aabb["center"], "radius": rad, "height": max(h, 2 * rad)}
    return {"aabb": aabb, "obb": obb, "sphere": sphere, "capsule_y": capsule,
            "godot": {"BoxShape3D.size": aabb["size"], "SphereShape3D.radius": sphere["radius"],
                      "CapsuleShape3D.radius": rad, "CapsuleShape3D.height": capsule["height"]}}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Collision primitives from GLB.")
    ap.add_argument("glb"); ap.add_argument("-o", "--out"); ap.add_argument("--per-node", action="store_true")
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
    _src_keys = ('glb',)
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

    g, b = load_glb(a.glb); parts = world_vertices(g, b)
    if not parts: raise SystemExit("no meshes in the default scene")
    res = {"file": a.glb, "all": shapes(np.concatenate([v for _, v in parts]))}
    if a.per_node: res["nodes"] = {n: shapes(v) for n, v in parts}
    txt = json.dumps(res, indent=1)
    (open(a.out, "w").write(txt) if a.out else print(txt))
    s = res["all"]["aabb"]["size"]
    print(f"aabb size {[round(x, 3) for x in s]}, sphere r={res['all']['sphere']['radius']:.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
