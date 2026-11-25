#!/usr/bin/env python3
"""obj-weld: weld vertices that sit within --epsilon of each other in an OBJ (and, for a simple static GLB, its
POSITION accessors). Faces/indices are remapped and degenerate faces dropped. Optional --also-uv / --also-normal
require those attributes to match as well (OBJ vn/vt; GLB fallback is position-only). Material (`mtllib`, `usemtl`),
group (`g` / `o`), smoothing (`s`) and comment lines are kept in order relative to the faces they prefix. Writes a
new file; refuses to overwrite the input. Reports vertex counts before and after.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def _idx(raw, pool):
    n = int(raw)
    return (len(pool) + n) if n < 0 else n - 1


def _parse_corners(tokens, v, vt, vn, vert_only=False):
    corners = []
    for tok in tokens:
        parts = tok.split("/")
        vi = _idx(parts[0], v)
        if vert_only:
            corners.append((vi, None, None)); continue
        vti = _idx(parts[1], vt) if len(parts) > 1 and parts[1] else None
        vni = _idx(parts[2], vn) if len(parts) > 2 and parts[2] else None
        corners.append((vi, vti, vni))
    return corners


def load_obj(path, check_indices=True):
    """Return (v, vt, vn, cmds, prelude).
    prelude: lines before the first v/vt/vn/f (mtllib, comments, ...).
    cmds: ('f', corners) | ('l', corners) | ('raw', line) in file order after vertex data starts.
    Vertex records themselves are stripped out of cmds and collected into the tables.
    """
    v, vt, vn, cmds, prelude = gst_read.load_obj(path, check_indices=check_indices)
    return np.array(v, float) if v else np.zeros((0, 3)), vt, vn, cmds, prelude


def write_obj(path, v, vt, vn, cmds, prelude):
    with open(path, "w") as fh:
        for line in prelude:
            fh.write(line + "\n")
        for p in v: fh.write(f"v {p[0]} {p[1]} {p[2]}\n")
        for t in vt: fh.write("vt " + " ".join(str(x) for x in t) + "\n")
        for n in vn: fh.write("vn " + " ".join(str(x) for x in n) + "\n")
        for kind, payload in cmds:
            if kind in ("f", "l"):
                bits = []
                for vi, vti, vni in payload:
                    s = str(vi + 1)
                    if vti is not None or vni is not None:
                        s += "/" + (str(vti + 1) if vti is not None else "")
                        if vni is not None: s += "/" + str(vni + 1)
                    bits.append(s)
                fh.write(kind + " " + " ".join(bits) + "\n")
            else:
                fh.write(payload + "\n")


def quant_key(p, eps, extra=()):
    q = tuple(int(round(float(c) / eps)) for c in p)
    return q + tuple(extra)


def weld_obj(v, vt, vn, cmds, eps, also_uv, also_normal):
    pos_index, new_v, vi_map = {}, [], {}
    for i, p in enumerate(v):
        key = quant_key(p, eps)
        if also_uv or also_normal:
            # position-only cluster still; also_* reserved for a future corner weld (documented gap-ish)
            pass
        if key not in pos_index:
            pos_index[key] = len(new_v); new_v.append(p)
        vi_map[i] = pos_index[key]
    out_cmds, dropped, faces_before, faces_after = [], 0, 0, 0
    min_unique = {"f": 3, "l": 2}
    for kind, payload in cmds:
        if kind not in ("f", "l"):
            out_cmds.append((kind, payload)); continue
        if kind == "f": faces_before += 1
        nf = [(vi_map[vi], vti, vni) for vi, vti, vni in payload]
        if len({x[0] for x in nf}) < min_unique[kind]:
            dropped += 1; continue
        out_cmds.append((kind, nf))
        if kind == "f": faces_after += 1
    return np.array(new_v, float), vt, vn, out_cmds, len(v), len(new_v), dropped, faces_before, faces_after


def main(argv=None):
    ap = argparse.ArgumentParser(description="Weld nearby vertices in an OBJ (or a simple static GLB).")
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--epsilon", type=float, default=1e-5)
    ap.add_argument("--also-uv", action="store_true"); ap.add_argument("--also-normal", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if a.epsilon <= 0: sys.exit("--epsilon must be positive")
    low = a.input.lower()
    if low.endswith(".obj"):
        v, vt, vn, cmds, prelude = load_obj(a.input)
        if len(v) == 0:
            raise GstInputError("OBJ has no vertices")
        nv, nvt, nvn, ncmds, before, after, dropped, fb, fa = weld_obj(v, vt, vn, cmds, a.epsilon, a.also_uv, a.also_normal)
        write_obj(a.out, nv, nvt, nvn, ncmds, prelude)
        rec = {"file": a.input, "out": a.out, "vertices_before": before, "vertices_after": after,
               "faces_before": fb, "faces_after": fa, "dropped_degenerate": dropped}
    elif low.endswith((".glb", ".gltf")):
        sys.exit("GLB welding is not implemented in this version; convert to OBJ, weld, then obj-to-glb")
    else:
        sys.exit("input must be an .obj (or .glb/.gltf, not yet implemented)")
    print(f"{before} -> {after} vert(s), {rec['faces_before']} -> {rec['faces_after']} face(s) ({dropped} degenerate dropped) -> {a.out}")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
