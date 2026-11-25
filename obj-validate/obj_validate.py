#!/usr/bin/env python3
"""obj-validate: check an OBJ for out-of-range face indices, degenerate faces
(duplicate corners or zero area), unreferenced vertices, and vn/vt index
errors. Prints a report and exits 1 when errors are present (warnings alone
exit 0 unless `--strict`). Optional `--json`. This is a checker, not a
rewriter.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def area3(p0, p1, p2):
    n = np.cross(np.asarray(p1, float) - p0, np.asarray(p2, float) - p0)
    return float(np.linalg.norm(n)) * 0.5


def validate(path, area_eps):
    v, vt, vn, cmds, prelude = obj_weld.load_obj(path, check_indices=False)
    errors, warnings = [], []
    n_f = 0
    used_v, used_vt, used_vn = set(), set(), set()
    if len(v) == 0:
        errors.append({"code": "no-vertices", "msg": "OBJ has no vertices"})
    for kind, payload in cmds:
        if kind != "f":
            continue
        n_f += 1
        vis = [t[0] for t in payload]
        if any(i is None or i < 0 or i >= len(v) for i in vis):
            errors.append({"code": "bad-index", "face": n_f, "msg": f"face {n_f} has a vertex index out of range"})
            continue
        if len(set(vis)) < len(vis):
            errors.append({"code": "degenerate", "face": n_f, "msg": f"face {n_f} repeats a vertex"})
        if len(vis) >= 3:
            # fan from v0; any triangle of zero area is degenerate
            p0 = v[vis[0]]
            zero = True
            for a, b in zip(vis[1:], vis[2:]):
                if area3(p0, v[a], v[b]) > area_eps:
                    zero = False
                    break
            if zero:
                errors.append({"code": "degenerate", "face": n_f, "msg": f"face {n_f} has zero area"})
        for vi, vti, vni in payload:
            used_v.add(vi)
            if vti is not None:
                if vti < 0 or vti >= len(vt):
                    errors.append({"code": "bad-vt", "face": n_f, "msg": f"face {n_f} has a vt index out of range"})
                else:
                    used_vt.add(vti)
            if vni is not None:
                if vni < 0 or vni >= len(vn):
                    errors.append({"code": "bad-vn", "face": n_f, "msg": f"face {n_f} has a vn index out of range"})
                else:
                    used_vn.add(vni)
    if n_f == 0:
        errors.append({"code": "no-faces", "msg": "OBJ has no faces"})
    unused_v = [i for i in range(len(v)) if i not in used_v]
    if unused_v:
        warnings.append({"code": "unused-vertices", "count": len(unused_v),
                         "msg": f"{len(unused_v)} unreferenced vertex(es)"})
    rec = {"file": path, "vertices": len(v), "faces": n_f, "uvs": len(vt), "normals": len(vn),
           "errors": errors, "warnings": warnings,
           "ok": not errors}
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate an OBJ for index and degenerate-face errors.")
    ap.add_argument("input")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--area-eps", type=float, default=1e-12, help="minimum triangle area (default: 1e-12)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    rec = validate(a.input, a.area_eps)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    n_err, n_warn = len(rec["errors"]), len(rec["warnings"])
    print(f"{rec['vertices']} vert(s), {rec['faces']} face(s), {n_err} error(s), {n_warn} warning(s)")
    for e in rec["errors"]:
        print("error:", e["msg"])
    for w in rec["warnings"]:
        print("warning:", w["msg"])
    if rec["errors"] or (a.strict and rec["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
