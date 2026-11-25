#!/usr/bin/env python3
"""obj-drop-unused: drop unreferenced v / vt / vn records from a Wavefront OBJ
and remap face (and line) corners. Positions that are used, material / group /
smoothing lines and the prelude are kept. The input is never overwritten unless
`--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402
from gst_errors import GstInputError  # noqa: E402


def compact(table, used):
    """Return (new_table, old_index -> new_index)."""
    mapping = {}
    out = []
    for i, rec in enumerate(table):
        if i in used:
            mapping[i] = len(out)
            out.append(rec)
    return out, mapping


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Drop unreferenced OBJ vertices, UVs and normals.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)

    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    if len(v) == 0:
        raise GstInputError("OBJ has no vertices")
    used_v, used_vt, used_vn = set(), set(), set()
    for kind, payload in cmds:
        if kind in ("f", "l"):
            for vi, vti, vni in payload:
                if vi is not None:
                    used_v.add(vi)
                if vti is not None:
                    used_vt.add(vti)
                if vni is not None:
                    used_vn.add(vni)
    nv, map_v = compact(list(v), used_v)
    nvt, map_vt = compact(list(vt), used_vt)
    nvn, map_vn = compact(list(vn), used_vn)
    new_cmds = []
    for kind, payload in cmds:
        if kind in ("f", "l"):
            corners = []
            for vi, vti, vni in payload:
                corners.append((
                    map_v[vi] if vi is not None else None,
                    map_vt[vti] if vti is not None else None,
                    map_vn[vni] if vni is not None else None,
                ))
            new_cmds.append((kind, corners))
        else:
            new_cmds.append((kind, payload))
    rec = {
        "out": a.out,
        "v": {"before": int(len(v)), "after": len(nv), "dropped": int(len(v)) - len(nv)},
        "vt": {"before": len(vt), "after": len(nvt), "dropped": len(vt) - len(nvt)},
        "vn": {"before": len(vn), "after": len(nvn), "dropped": len(vn) - len(nvn)},
    }
    import numpy as np
    obj_weld.write_obj(a.out, np.asarray(nv, float) if nv else np.zeros((0, 3)), nvt, nvn, new_cmds, prelude)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("dropped v=%d vt=%d vn=%d -> %s" % (
        rec["v"]["dropped"], rec["vt"]["dropped"], rec["vn"]["dropped"], a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
