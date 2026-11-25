#!/usr/bin/env python3
"""obj-uv-unwrap: give an OBJ that has no UVs a first set of texture coordinates, so it can go through obj-to-glb and
a texture pipeline. This is projection, not a real unwrapper: good for blockout, props and architecture, not organic models.
box:    every face goes to the island of its dominant axis (+X -X +Y -Y +Z -Z), projected flat, islands laid out in a 3x2
        grid of square cells (the lower two thirds of the UV square stay free) with --padding. Texel density is
        uniform and isotropic on a square texture (all islands share one scale). Faces on the same axis can overlap in
        UV space on concave meshes; check with uv-check.
planar: the whole mesh is projected along one --axis onto the 0..1 square (back faces overlap the front).
Positions, normals, groups, materials and face order are preserved. Faces keep their vertices; UVs are per face corner.
An OBJ that already has `vt` is refused unless --force.
"""
import argparse, os, sys, sys
import numpy as np


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def parse(path):
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines(); V = []
    for ln in lines:
        p = ln.split()
        if p and p[0] == "v": V.append(gst_read._obj_floats(p[1:], 3, "vertex"))
    return lines, (np.array(V, float) if V else np.zeros((0, 3)))


def face_corners(tok):
    return [t.split("/") for t in tok]


def poly_normal(P):
    n = np.zeros(3)
    for i in range(len(P)): a, b = P[i], P[(i + 1) % len(P)]; n += [(a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1])]
    return n


AX = {0: (2, 1), 1: (0, 2), 2: (0, 1)}      # projected (u, v) axes for a face whose dominant axis is x / y / z


def unwrap(lines, V, mode="box", axis="y", padding=0.02, force=False):
    if any(l.startswith("vt ") for l in lines) and not force: raise SystemExit("the OBJ already has UVs (use --force to replace them)")
    lo, hi = V.min(0), V.max(0); ext = np.maximum(hi - lo, 1e-9); big = ext.max()
    out, vt, uv_index = [], [], {}
    body = []
    for ln in lines:
        p = ln.split()
        if p and p[0] == "vt": continue
        if p and p[0] == "f":
            idx = [int(t.split("/")[0]) for t in p[1:]]; idx = [i - 1 if i > 0 else len(V) + i for i in idx]; P = V[idx]; n = poly_normal(P)
            if mode == "box":
                a = int(np.argmax(np.abs(n))); neg = n[a] < 0; isl = a * 2 + (1 if neg else 0); u_ax, v_ax = AX[a]
                cw = ch = 1 / 3; col, row = isl % 3, isl // 3; inner = 1 - 2 * padding
                uvs = []
                for q in P:
                    u = (q[u_ax] - lo[u_ax]) / big; v = (q[v_ax] - lo[v_ax]) / big
                    if neg: u = ext[u_ax] / big - u
                    uvs.append((col * cw + padding * cw + u * cw * inner, row * ch + padding * ch + v * ch * inner))
            else:
                ai = "xyz".index(axis); u_ax, v_ax = AX[ai]
                uvs = [((q[u_ax] - lo[u_ax]) / ext[u_ax], (q[v_ax] - lo[v_ax]) / ext[v_ax]) for q in P]
            toks = []
            for t, uv in zip(p[1:], uvs):
                parts = t.split("/"); key = (round(uv[0], 6), round(uv[1], 6))
                if key not in uv_index: uv_index[key] = len(vt) + 1; vt.append(key)
                toks.append("/".join([parts[0], str(uv_index[key])] + ([parts[2]] if len(parts) > 2 and parts[2] else [])))
            body.append("f " + " ".join(toks))
        else: body.append(ln)
    first_f = next((i for i, l in enumerate(body) if l.startswith(("f ", "usemtl", "g ", "o ", "s "))), len(body))
    out = body[:first_f] + [f"vt {u:.6f} {v:.6f}" for u, v in vt] + body[first_f:]
    return "\n".join(out) + "\n", len(vt)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Project UVs onto an OBJ that has none.")
    ap.add_argument("obj"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--mode", choices=["box", "planar"], default="box")
    ap.add_argument("--axis", choices=["x", "y", "z"], default="y", help="planar projection axis"); ap.add_argument("--padding", type=float, default=0.02); ap.add_argument("--force", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.obj) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    lines, V = parse(a.obj)
    if len(V) == 0: sys.exit("no vertices")
    text, n = unwrap(lines, V, a.mode, a.axis, a.padding, a.force); open(a.out, "w", encoding="utf-8").write(text)
    print(f"{a.mode} projection: {n} UV coordinate(s) -> {a.out}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
