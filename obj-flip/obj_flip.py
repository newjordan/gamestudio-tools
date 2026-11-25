#!/usr/bin/env python3
"""obj-flip: mirror an OBJ across an axis (`--axis x|y|z`). Vertex positions and
normals are negated on that axis; triangle winding is reversed so the mesh does
not turn inside-out. mtllib, usemtl, groups and smoothing lines are kept. The
input is never overwritten unless `--in-place`.
"""
import argparse, os, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def flip(v, vn, cmds, axis):
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    pos = np.array(v, float)
    if len(pos):
        pos[:, ax] *= -1
    nrm = [list(row) for row in vn]
    for row in nrm:
        if len(row) >= 3:
            row[ax] = -row[ax]
            n = float(np.linalg.norm(row[:3])) or 1.0
            row[0], row[1], row[2] = row[0] / n, row[1] / n, row[2] / n
    out = []
    n_f = 0
    for kind, payload in cmds:
        if kind in ("f", "l"):
            out.append((kind, list(reversed(payload))))
            if kind == "f":
                n_f += 1
        else:
            out.append((kind, payload))
    return pos.tolist() if hasattr(pos, "tolist") else pos, nrm, out, n_f


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mirror an OBJ across an axis, reversing face winding.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--axis", choices=("x", "y", "z"), required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    if len(v) == 0:
        sys.exit("OBJ has no vertices")
    new_v, new_vn, new_cmds, n_f = flip(v, vn, cmds, a.axis)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, new_v, vt, new_vn, new_cmds, prelude)
    rec = {"out": a.out, "axis": a.axis, "vertices": len(new_v), "faces": n_f}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json_mod = __import__("json")
        json_mod.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(new_v)} vert(s), {n_f} face(s) flipped on {a.axis} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
