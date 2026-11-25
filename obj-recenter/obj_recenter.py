#!/usr/bin/env python3
"""obj-recenter: move an OBJ so its bounding-box centre, bottom (feet) or min corner sits at the origin.
`--up y|z` picks the up axis for `--mode bottom`. Vertex colours and all non-`v` lines (mtllib, usemtl, groups,
smoothing, comments, faces) are kept. The input is never overwritten. Sibling of mesh-pivot-fix, OBJ only.
"""
import argparse, os, sys, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import mesh_pivot_fix  # noqa: E402


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def main(argv=None):
    ap = argparse.ArgumentParser(description="Recenter an OBJ at its bbox centre, bottom (feet), or min corner.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--mode", choices=("center", "centre", "bottom", "min"), default="center")
    ap.add_argument("--up", choices=("y", "z"), default="y", help="up axis for --mode bottom")
    ap.add_argument("--report", action="store_true", help="print bounds and write nothing")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if not a.input.lower().endswith(".obj"):
        sys.exit("obj-recenter is OBJ only (use mesh-pivot-fix for glTF/GLB)")
    mode = "center" if a.mode == "centre" else a.mode
    if a.report:
        verts = []
        for l in open(a.input, encoding="utf-8", errors="replace"):
            if l.startswith("v "):
                verts.append(gst_read._obj_floats(l.split()[1:], 3, "vertex"))
        if not verts: sys.exit("OBJ has no vertices")
        A = np.array(verts); lo, hi = A.min(0), A.max(0)
        rec = {"before": {"min": lo.tolist(), "max": hi.tolist()}}
        print(f"bounds min {mesh_pivot_fix.fmt(lo)} max {mesh_pivot_fix.fmt(hi)}")
        if a.json: json.dump(rec, open(a.json, "w"), indent=1)
        return 0
    if os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    rec = mesh_pivot_fix.fix_obj(a.input, a.out, mode, a.up)
    rec["out"] = a.out; rec["mode"] = mode; rec["up"] = a.up
    print(f"before: min {mesh_pivot_fix.fmt(rec['before']['min'])} max {mesh_pivot_fix.fmt(rec['before']['max'])}")
    print(f"after:  min {mesh_pivot_fix.fmt(rec['after']['min'])} max {mesh_pivot_fix.fmt(rec['after']['max'])}")
    print(f"shift {mesh_pivot_fix.fmt(rec['shift'])} -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
