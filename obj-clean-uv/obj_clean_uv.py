#!/usr/bin/env python3
"""obj-clean-uv: clean Wavefront OBJ texture coordinates. Optionally clamp to
the 0–1 square, weld duplicate UVs within an epsilon, and drop unreferenced
vt records, remapping face corners. Positions, normals, mtllib, usemtl, groups
and smoothing lines are kept. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402
from gst_errors import GstInputError  # noqa: E402


def clean(v, vt, vn, cmds, clamp, weld_eps, drop_unused):
    vt = [list(t) for t in vt]
    clamped = 0
    if clamp:
        for t in vt:
            nu = min(1.0, max(0.0, t[0]))
            nv = min(1.0, max(0.0, t[1] if len(t) > 1 else 0.0))
            if nu != t[0] or (len(t) > 1 and nv != t[1]):
                clamped += 1
            t[0] = nu
            if len(t) > 1:
                t[1] = nv
    welded = 0
    remap = list(range(len(vt)))
    if weld_eps is not None and weld_eps >= 0 and vt:
        buckets = {}
        new_vt = []
        for i, t in enumerate(vt):
            key = tuple(int(round(x / weld_eps)) if weld_eps > 0 else x for x in t[:2])
            if key in buckets:
                remap[i] = buckets[key]
                welded += 1
            else:
                buckets[key] = len(new_vt)
                remap[i] = len(new_vt)
                new_vt.append(t)
        vt = new_vt
        new_cmds = []
        for kind, payload in cmds:
            if kind == "f":
                corners = []
                for vi, vti, vni in payload:
                    if vti is not None:
                        vti = remap[vti]
                    corners.append((vi, vti, vni))
                new_cmds.append((kind, corners))
            else:
                new_cmds.append((kind, payload))
        cmds = new_cmds
    dropped = 0
    if drop_unused:
        used = set()
        for kind, payload in cmds:
            if kind == "f":
                for _vi, vti, _vni in payload:
                    if vti is not None:
                        used.add(vti)
        if len(used) != len(vt):
            keep = sorted(used)
            idx = {old: i for i, old in enumerate(keep)}
            dropped = len(vt) - len(keep)
            vt = [vt[i] for i in keep]
            new_cmds = []
            for kind, payload in cmds:
                if kind == "f":
                    corners = []
                    for vi, vti, vni in payload:
                        if vti is not None:
                            vti = idx[vti]
                        corners.append((vi, vti, vni))
                    new_cmds.append((kind, corners))
                else:
                    new_cmds.append((kind, payload))
            cmds = new_cmds
    return v, vt, vn, cmds, {"clamped": clamped, "welded": welded, "dropped": dropped, "uvs": len(vt)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Clean unused, duplicate, or out-of-range UVs on a Wavefront OBJ.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clamp", action="store_true", help="clamp vt u,v to the 0-1 square")
    ap.add_argument("--weld", type=float, default=None, metavar="EPS",
                    help="weld UVs whose components agree within EPS (0 merges exact copies)")
    ap.add_argument("--keep-unused", action="store_true", help="do not drop unreferenced vt records")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    if len(v) == 0:
        raise GstInputError("OBJ has no vertices")
    v, vt, vn, cmds, rec = clean(v, vt, vn, cmds, a.clamp, a.weld, not a.keep_unused)
    rec["out"] = a.out
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, v, vt, vn, cmds, prelude)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("cleaned UVs: clamped %(clamped)s, welded %(welded)s, dropped %(dropped)s, kept %(uvs)s -> %(out)s" % rec)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
