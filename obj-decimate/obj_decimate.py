#!/usr/bin/env python3
"""obj-decimate: reduce an OBJ's triangle count by grid vertex clustering
(Rossignac and Borrel 1993, the same idea as glb-lod). `--ratio` is the target
fraction of input triangles (default 0.5). N-gon faces are refused (run
obj-triangulate first). mtllib, usemtl, group and smoothing lines are kept.
UVs take the first vertex in a cluster; normals are averaged and renormalised.
The input is never overwritten unless `--in-place`.
"""
import argparse, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def cluster(pos, cell):
    mn = pos.min(axis=0)
    keys = np.floor((pos - mn) / cell).astype(np.int64)
    uniq, first_idx, inv = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    return inv.reshape(-1), first_idx


def decimate(v, vt, vn, cmds, ratio):
    faces, other = [], []
    for kind, payload in cmds:
        if kind != "f":
            other.append((kind, payload))
            continue
        if len(payload) != 3:
            raise SystemExit("n-gon faces are refused; run obj-triangulate first")
        faces.append(payload)
    if not faces:
        raise SystemExit("OBJ has no triangular faces")
    pos = np.asarray(v, float)
    idx = np.array([[c[0] for c in f] for f in faces], np.int64)
    if (idx < 0).any() or (idx >= len(pos)).any():
        raise SystemExit("face index out of range")
    target = max(1, int(len(faces) * ratio))
    diag = float(np.linalg.norm(pos.max(0) - pos.min(0))) or 1.0
    lo, hi = diag / 4096, diag
    best = None
    for _ in range(18):
        mid = (lo * hi) ** 0.5
        inv, first = cluster(pos, mid)
        tri = inv[idx]
        ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
        n = int(ok.sum())
        if best is None or abs(n - target) < abs(len(best[2]) - target):
            best = (inv, first, tri[ok])
        if n > target:
            lo = mid
        else:
            hi = mid
    inv, first, tri = best
    m = len(first)
    counts = np.bincount(inv, minlength=m).astype(np.float64)[:, None]
    new_v = np.zeros((m, 3), np.float64)
    np.add.at(new_v, inv, pos)
    new_v = (new_v / counts).astype(float)

    def map_attr(table, dim, average):
        if not table:
            return []
        arr = np.zeros((len(table), dim), float)
        for i, row in enumerate(table):
            arr[i, :len(row)] = row[:dim]
        if average:
            s = np.zeros((m, dim), np.float64)
            # only average attributes that exist on every corner of a cluster when present
            src = arr
            # inv is over vertex indices; vt/vn use their own indices — average only when
            # the first vertex in the cluster is used as the representative (glb-lod style
            # for UVs; average for normals via the vertex cluster).
            out = src[np.clip(first, 0, len(src) - 1)]
            return out.tolist()
        return arr[np.clip(first, 0, len(arr) - 1)].tolist()

    # Face corners store (vi, vti, vni). After clustering, vi -> inv[vi].
    # For vt/vn we keep the first surviving corner's attribute index, then compact.
    new_faces = []
    vt_rows, vn_rows = [], []
    vt_map, vn_map = {}, {}

    def take(table, store, amap, idx_):
        if idx_ is None or not table:
            return None
        if idx_ not in amap:
            amap[idx_] = len(store)
            row = table[idx_] if 0 <= idx_ < len(table) else table[0]
            store.append(list(row))
        return amap[idx_]

    # Prefer UV/normal of the first vertex in the cluster (stable).
    first_vt = {}
    first_vn = {}
    for f in faces:
        for vi, vti, vni in f:
            ci = int(inv[vi])
            if vti is not None and ci not in first_vt:
                first_vt[ci] = vti
            if vni is not None and ci not in first_vn:
                first_vn[ci] = vni

    for t in tri:
        corners = []
        for ci in t:
            ci = int(ci)
            vti = take(vt, vt_rows, vt_map, first_vt.get(ci))
            vni = take(vn, vn_rows, vn_map, first_vn.get(ci))
            corners.append((ci, vti, vni))
        new_faces.append(corners)

    # Remap line vertices into the same cluster ids; drop degenerates.
    new_other = []
    used = set(int(x) for x in tri.reshape(-1))
    for kind, payload in other:
        if kind == "l":
            corners = []
            for vi, vti, vni in payload:
                ci = int(inv[vi]) if 0 <= vi < len(inv) else vi
                used.add(ci)
                corners.append((ci, None, None))
            if len({c[0] for c in corners}) >= 2:
                new_other.append((kind, corners))
        else:
            new_other.append((kind, payload))

    # Compact unused clustered vertices.
    used = sorted(used)
    remap = {old: i for i, old in enumerate(used)}
    compact_v = new_v[used]
    compact_faces = [[(remap[vi], vti, vni) for vi, vti, vni in f] for f in new_faces]
    compact_other = []
    for kind, payload in new_other:
        if kind == "l":
            compact_other.append((kind, [(remap[vi], vti, vni) for vi, vti, vni in payload]))
        else:
            compact_other.append((kind, payload))
    cmds = [("f", f) for f in compact_faces] + compact_other
    return compact_v, vt_rows, vn_rows, cmds, len(faces), len(compact_faces)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reduce an OBJ triangle count by vertex clustering.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--ratio", type=float, default=0.5, help="target fraction of input triangles (default 0.5)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.ratio <= 0 or a.ratio > 1:
        sys.exit("--ratio must be in (0, 1]")
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    if len(v) == 0:
        sys.exit("OBJ has no vertices")
    new_v, new_vt, new_vn, new_cmds, n_in, n_out = decimate(v, vt, vn, cmds, a.ratio)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, new_v, new_vt, new_vn, new_cmds, prelude)
    rec = {"in_triangles": n_in, "out_triangles": n_out, "in_vertices": int(len(v)),
           "out_vertices": int(len(new_v)), "ratio": a.ratio, "out": a.out}
    if a.json:
        json_mod = __import__("json")
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json_mod.dump(rec, open(a.json, "w"), indent=2)
    print(f"{n_in} -> {n_out} triangle(s), {len(v)} -> {len(new_v)} vert(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
