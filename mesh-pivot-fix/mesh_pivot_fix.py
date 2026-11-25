#!/usr/bin/env python3
"""mesh-pivot-fix: move a model's pivot (its origin) to a sensible place - bounding-box centre, bottom centre ("feet"),
the min corner, or a given point - and report the bounds before and after. GLB/glTF: the world-space bounds come from the
POSITION accessors' min/max with every node transform applied; the fix shifts each root node of the scene by the pivot offset,
which is exact for any hierarchy and leaves vertex data and animation of child nodes untouched (warns when a skin or an animation
targets a root node, because those can override the shift). OBJ: vertex positions are translated directly.
Y is up (glTF convention); use --up z for Z-up OBJ files so "bottom" means min Z.
"""
import argparse, os, json, math, struct, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def read_glb(path):
    js, _bin, ver, chunks = gst_read.load_gltf_or_glb(path)
    return js, chunks, ver


def write_glb(path, js, chunks, ver):
    blob = json.dumps(js, separators=(",", ":")).encode("utf-8"); blob += b" " * (-len(blob) % 4)
    out = [(b"JSON", blob)] + [(t, c) for t, c in chunks if t != b"JSON"]
    total = 12 + sum(8 + len(c) for _, c in out)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", ver, total))
        for t, c in out: f.write(struct.pack("<I4s", len(c), t) + c)


def local_matrix(n):
    if "matrix" in n: return np.array(n["matrix"], float).reshape(4, 4).T          # glTF is column-major
    t = n.get("translation", [0, 0, 0]); q = n.get("rotation", [0, 0, 0, 1]); s = n.get("scale", [1, 1, 1])
    x, y, z, w = q; nrm = math.sqrt(x * x + y * y + z * z + w * w) or 1; x, y, z, w = x / nrm, y / nrm, z / nrm, w / nrm
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * np.array(s)[None, :]; M[:3, 3] = t
    return M


def scene_roots(js):
    scenes = js.get("scenes") or []
    if scenes: return list(scenes[js.get("scene", 0)].get("nodes", []))
    children = {c for n in js.get("nodes", []) for c in n.get("children", [])}
    return [i for i in range(len(js.get("nodes", []))) if i not in children]


def world_bounds(js):
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf); nodes = js.get("nodes", [])
    def walk(i, parent):
        nonlocal lo, hi
        M = parent @ local_matrix(nodes[i])
        if "mesh" in nodes[i]:
            for p in js["meshes"][nodes[i]["mesh"]].get("primitives", []):
                acc = js["accessors"][p["attributes"]["POSITION"]]
                if "min" not in acc or "max" not in acc: raise SystemExit("POSITION accessor has no min/max (required by the glTF spec); cannot compute bounds")
                mn, mx = acc["min"], acc["max"]
                for cx in (mn[0], mx[0]):
                    for cy in (mn[1], mx[1]):
                        for cz in (mn[2], mx[2]):
                            v = (M @ np.array([cx, cy, cz, 1.0]))[:3]; lo = np.minimum(lo, v); hi = np.maximum(hi, v)
        for c in nodes[i].get("children", []): walk(c, M)
    for r in scene_roots(js): walk(r, np.eye(4))
    if not np.isfinite(lo).all(): raise SystemExit("no meshes found in the scene")
    return lo, hi


def pivot_point(lo, hi, mode, up="y", offset=None):
    c = (lo + hi) / 2; ax = {"y": 1, "z": 2}[up]
    if mode == "center": return c
    if mode == "bottom": p = c.copy(); p[ax] = lo[ax]; return p
    if mode == "min": return lo.copy()
    if mode == "point": return np.array(offset, float)
    raise SystemExit(f"unknown mode {mode}")


def fix_gltf(js, mode, offset=None):
    lo, hi = world_bounds(js); p = pivot_point(lo, hi, mode, "y", offset); warns = []
    roots = scene_roots(js); nodes = js["nodes"]
    if js.get("skins"): warns.append("the file has skins; joint transforms may need the same shift (check the result in your viewer)")
    for an in js.get("animations", []):
        for ch in an.get("channels", []):
            if ch.get("target", {}).get("node") in roots and ch["target"].get("path") == "translation":
                warns.append(f"animation {an.get('name', '')!r} drives a root node's translation and will override the pivot shift"); break
    for r in roots:
        n = nodes[r]
        if "matrix" in n: m = list(n["matrix"]); m[12] -= p[0]; m[13] -= p[1]; m[14] -= p[2]; n["matrix"] = m
        else: t = list(n.get("translation", [0, 0, 0])); n["translation"] = [t[0] - p[0], t[1] - p[1], t[2] - p[2]]
    nlo, nhi = world_bounds(js)
    return {"before": {"min": lo.tolist(), "max": hi.tolist()}, "after": {"min": nlo.tolist(), "max": nhi.tolist()}, "shift": (-p).tolist(), "warnings": warns}


def fix_obj(src, dst, mode, up="y", offset=None):
    lines = open(src, encoding="utf-8", errors="replace").read().splitlines(keepends=False)
    V = [(i, gst_read._obj_floats(l.split()[1:], 3, "vertex")) for i, l in enumerate(lines) if l.startswith("v ")]
    if not V: raise SystemExit("OBJ has no vertices")
    A = np.array([v for _, v in V]); lo, hi = A.min(0), A.max(0)
    if up == "z" and mode == "bottom": p = (lo + hi) / 2; p[2] = lo[2]
    else: p = pivot_point(lo, hi, mode, "y", offset)
    for i, v in V:
        extra = lines[i].split()[4:]            # keep optional vertex colours
        lines[i] = "v " + " ".join(f"{x:.6g}" if abs(x) > 1e-9 else "0" for x in (np.array(v) - p)) + (" " + " ".join(extra) if extra else "")
    open(dst, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return {"before": {"min": lo.tolist(), "max": hi.tolist()}, "after": {"min": (lo - p).tolist(), "max": (hi - p).tolist()}, "shift": (-p).tolist(), "warnings": []}


def fmt(v): return "(" + ", ".join(f"{x:.4g}" for x in v) + ")"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Move a model's pivot (bbox centre, feet, min corner or point).")
    ap.add_argument("input", help=".glb, .gltf or .obj"); ap.add_argument("-o", "--out", help="output path (default: <name>_pivot.<ext>)")
    ap.add_argument("--mode", choices=["center", "bottom", "min", "point"], default="bottom"); ap.add_argument("--point", help="x,y,z for --mode point (world space, before the fix)")
    ap.add_argument("--up", choices=["y", "z"], default="y", help="up axis for OBJ 'bottom'"); ap.add_argument("--report", action="store_true", help="only print the bounds, write nothing")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    off = [float(x) for x in a.point.split(",")] if a.point else None
    if a.mode == "point" and (off is None or len(off) != 3): sys.exit("--mode point needs --point x,y,z")
    ext = os.path.splitext(a.input)[1].lower(); out = a.out or os.path.splitext(a.input)[0] + "_pivot" + ext
    if os.path.abspath(out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    if ext == ".obj":
        if a.report:
            A = np.array([gst_read._obj_floats(l.split()[1:], 3, "vertex") for l in open(a.input) if l.startswith("v ")]); print(f"bounds min {fmt(A.min(0))} max {fmt(A.max(0))}"); return 0
        r = fix_obj(a.input, out, a.mode, a.up, off)
    elif ext in (".glb", ".gltf"):
        js, chunks, ver = read_glb(a.input)
        if a.report:
            lo, hi = world_bounds(js); print(f"bounds min {fmt(lo)} max {fmt(hi)}"); return 0
        r = fix_gltf(js, a.mode, off)
        if chunks is None: json.dump(js, open(out, "w"), indent=1)
        else: write_glb(out, js, chunks, ver)
    else:
        sys.exit("unsupported file type (use .glb, .gltf or .obj)")
    print(f"before: min {fmt(r['before']['min'])} max {fmt(r['before']['max'])}\nafter:  min {fmt(r['after']['min'])} max {fmt(r['after']['max'])}\nshift {fmt(r['shift'])} -> {out}")
    for w in r["warnings"]: print("WARN " + w)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
