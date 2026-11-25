#!/usr/bin/env python3
"""obj-normals: recompute vertex normals on an OBJ as flat (one normal per face) or
smooth (averaged at each vertex, optionally split by an angle threshold and by smoothing
groups). `s off` / `s 0` faces stay flat even in smooth mode. Material (`mtllib`,
`usemtl`), group (`g` / `o`) and comment lines are kept. Writes a new OBJ; the input is
never overwritten unless `--in-place`.
"""
import argparse, os, json, math, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def face_normal(v, corners):
    pts = [np.asarray(v[c[0]], float) for c in corners]
    n = np.zeros(3, float)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    L = float(np.linalg.norm(n))
    if L < 1e-12 and len(pts) >= 3:
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        L = float(np.linalg.norm(n))
    if L < 1e-12:
        return np.array([0.0, 0.0, 1.0])
    return n / L


def parse_sgroup(line):
    bits = line.strip().split()
    if len(bits) < 2:
        return "off"
    tok = bits[1].lower()
    return "off" if tok in ("off", "0") else bits[1]


def recompute(v, vt, vn, cmds, mode, angle_deg=None):
    cmds = list(cmds)
    sg = "1"
    faces = []  # (cmd_index, corners, sgroup)
    for i, (kind, payload) in enumerate(cmds):
        if kind == "raw" and str(payload).strip().startswith("s "):
            sg = parse_sgroup(payload)
        if kind == "f":
            faces.append((i, payload, sg))
    fnorms = [face_normal(v, corners) for _, corners, _ in faces]
    new_vn = []
    cache = {}  # key -> vn index

    def add_normal(vec, key=None):
        if key is not None and key in cache:
            return cache[key]
        idx = len(new_vn)
        new_vn.append(np.asarray(vec, float))
        if key is not None:
            cache[key] = idx
        return idx

    if mode == "flat":
        for (ci, corners, _sg), n in zip(faces, fnorms):
            idx = add_normal(n)
            cmds[ci] = ("f", [(vi, vti, idx) for vi, vti, _vni in corners])
    else:
        min_dot = None if angle_deg is None else math.cos(math.radians(float(angle_deg)))
        inc = {}
        for fi, (_ci, corners, sg) in enumerate(faces):
            if sg == "off":
                continue
            for vi, _vti, _vni in corners:
                inc.setdefault((vi, sg), []).append(fi)
        for fi, (ci, corners, sg) in enumerate(faces):
            new_corners = []
            n0 = fnorms[fi]
            for vi, vti, _vni in corners:
                if sg == "off":
                    idx = add_normal(n0, key=("flat", fi))
                else:
                    used = []
                    for fj in inc.get((vi, sg), [fi]):
                        if min_dot is None:
                            used.append(fj)
                        else:
                            d = float(np.clip(np.dot(n0, fnorms[fj]), -1.0, 1.0))
                            if d >= min_dot - 1e-12:
                                used.append(fj)
                    key = (vi, sg, tuple(sorted(set(used))))
                    if key in cache:
                        idx = cache[key]
                    else:
                        acc = np.zeros(3, float)
                        for fj in used:
                            acc += fnorms[fj]
                        L = float(np.linalg.norm(acc))
                        acc = acc / L if L > 1e-12 else n0
                        idx = add_normal(acc, key=key)
                new_corners.append((vi, vti, idx))
            cmds[ci] = ("f", new_corners)
    vn_out = [n.tolist() for n in new_vn]
    return vt, vn_out, cmds, {"normals": len(vn_out), "faces": len(faces), "mode": mode}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recompute flat or smooth vertex normals on an OBJ.")
    ap.add_argument("obj")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--mode", choices=("flat", "smooth"), default="smooth")
    ap.add_argument("--angle", type=float, help="max angle in degrees to average across (smooth mode)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.obj, a.out, a.in_place)
    if a.json:
        safe_out.check(a.obj, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.obj)
    if v is None or len(v) == 0:
        raise SystemExit("no vertices in OBJ")
    vt, vn_out, cmds, rec = recompute(v, vt, vn, cmds, a.mode, a.angle)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, v, vt, vn_out, cmds, prelude)
    rec.update({"out": a.out, "angle": a.angle})
    print(f"{rec['faces']} face(s), {rec['normals']} normal(s), mode {a.mode} -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
