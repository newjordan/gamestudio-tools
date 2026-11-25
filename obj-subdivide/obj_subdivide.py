#!/usr/bin/env python3
"""obj-subdivide: midpoint-subdivide every triangle in an OBJ (`--times`, default 1).
Each pass replaces a triangle with four; midpoints on shared edges are reused so the
mesh stays watertight. UVs and normals are interpolated when both endpoints have
them. N-gon faces are refused (run obj-triangulate first). mtllib, usemtl, groups
are kept. The input is never overwritten unless `--in-place`.
"""
import argparse, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def mid_attr(table, a, b):
    if a is None or b is None or not table:
        return None, None
    if not (0 <= a < len(table) and 0 <= b < len(table)):
        return None, None
    pa, pb = table[a], table[b]
    n = max(len(pa), len(pb))
    avg = [((pa[i] if i < len(pa) else 0) + (pb[i] if i < len(pb) else 0)) / 2 for i in range(n)]
    table.append(avg)
    return len(table) - 1, table


def subdivide_once(v, vt, vn, cmds):
    pos = [list(map(float, row[:3])) for row in v]
    vt = [list(row) for row in vt]
    vn = [list(row) for row in vn]
    edge_v, edge_vt, edge_vn = {}, {}, {}
    out_cmds = []
    faces_in = faces_out = 0

    def midpoint(i, j, ti, tj, ni, nj):
        key = (i, j) if i < j else (j, i)
        if key not in edge_v:
            a, b = pos[i], pos[j]
            pos.append([(a[k] + b[k]) / 2 for k in range(3)])
            edge_v[key] = len(pos) - 1
        mi = edge_v[key]
        # UV / normal midpoints are per-corner and may differ on a split seam
        ukey = (key, ti, tj)
        if ti is not None and tj is not None:
            if ukey not in edge_vt:
                idx, _ = mid_attr(vt, ti, tj)
                edge_vt[ukey] = idx
            mt = edge_vt[ukey]
        else:
            mt = None
        nkey = (key, ni, nj)
        if ni is not None and nj is not None:
            if nkey not in edge_vn:
                idx, _ = mid_attr(vn, ni, nj)
                if idx is not None:
                    # renormalise
                    vec = vn[idx]
                    if len(vec) >= 3:
                        nrm = float(np.linalg.norm(vec[:3])) or 1.0
                        vn[idx] = [vec[0] / nrm, vec[1] / nrm, vec[2] / nrm] + list(vec[3:])
                edge_vn[nkey] = idx
            mn = edge_vn[nkey]
        else:
            mn = None
        return mi, mt, mn

    for kind, payload in cmds:
        if kind != "f":
            out_cmds.append((kind, payload))
            continue
        if len(payload) != 3:
            raise SystemExit("n-gon faces are refused; run obj-triangulate first")
        faces_in += 1
        (i, ti, ni), (j, tj, nj), (k, tk, nk) = payload
        d = midpoint(i, j, ti, tj, ni, nj)
        e = midpoint(j, k, tj, tk, nj, nk)
        f = midpoint(k, i, tk, ti, nk, ni)
        # four triangles: i-d-f, j-e-d, k-f-e, d-e-f
        tris = [
            ((i, ti, ni), (d[0], d[1], d[2]), (f[0], f[1], f[2])),
            ((j, tj, nj), (e[0], e[1], e[2]), (d[0], d[1], d[2])),
            ((k, tk, nk), (f[0], f[1], f[2]), (e[0], e[1], e[2])),
            ((d[0], d[1], d[2]), (e[0], e[1], e[2]), (f[0], f[1], f[2])),
        ]
        for t in tris:
            out_cmds.append(("f", list(t)))
            faces_out += 1
    return pos, vt, vn, out_cmds, faces_in, faces_out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Midpoint-subdivide triangles in an OBJ.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--times", type=int, default=1, help="number of subdivision passes (default 1)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.times < 1:
        sys.exit("--times must be >= 1")
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    if len(v) == 0:
        sys.exit("OBJ has no vertices")
    n_in = sum(1 for k, p in cmds if k == "f")
    n_verts = len(v)
    faces_out = n_in
    for _ in range(a.times):
        v, vt, vn, cmds, _faces_in, faces_out = subdivide_once(v, vt, vn, cmds)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, v, vt, vn, cmds, prelude)
    rec = {"out": a.out, "times": a.times, "in_triangles": n_in, "out_triangles": faces_out,
           "in_vertices": n_verts, "out_vertices": len(v)}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json_mod = __import__("json")
        json_mod.dump(rec, open(a.json, "w"), indent=2)
    print(f"{n_in} -> {faces_out} triangle(s) after {a.times} pass(es) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
