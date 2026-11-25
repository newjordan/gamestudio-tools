#!/usr/bin/env python3
"""obj-triangulate: turn n-gon faces into triangles with ear-clipping so concave faces stay
inside the original polygon. Vertex / UV / normal index tokens are kept as written.
`mtllib`, `usemtl`, group (`g` / `o`), smoothing (`s`) and comment lines are copied through
in order. Writes a new OBJ; the input is never overwritten unless `--in-place`.
Self-intersecting or degenerate faces that cannot be ear-clipped fall back to a triangle fan
and are listed in the JSON report under `fan_fallback`.
"""
import argparse, os, sys, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def _v_index(token, nverts):
    raw = token.split("/")[0]
    if raw in ("", "."):
        raise SystemExit("face corner with no vertex index: " + token)
    n = int(raw)
    return (nverts + n) if n < 0 else n - 1


def _cross2(a, b, c):
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _area2(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a


def _project(pts):
    # Newell's method for a stable face normal, then drop the dominant axis.
    nx = ny = nz = 0.0
    n = len(pts)
    for i in range(n):
        ax, ay, az = pts[i]
        bx, by, bz = pts[(i + 1) % n]
        nx += (ay - by) * (az + bz)
        ny += (az - bz) * (ax + bx)
        nz += (ax - bx) * (ay + by)
    ax, ay, az = abs(nx), abs(ny), abs(nz)
    if ax >= ay and ax >= az:
        return [(p[1], p[2]) for p in pts]
    if ay >= ax and ay >= az:
        return [(p[0], p[2]) for p in pts]
    return [(p[0], p[1]) for p in pts]


def _point_in_tri(p, a, b, c):
    c1 = _cross2(a, b, p)
    c2 = _cross2(b, c, p)
    c3 = _cross2(c, a, p)
    has_neg = (c1 < -1e-14) or (c2 < -1e-14) or (c3 < -1e-14)
    has_pos = (c1 > 1e-14) or (c2 > 1e-14) or (c3 > 1e-14)
    return not (has_neg and has_pos)


def ear_clip(pts3, eps=1e-12):
    """Return a list of (i, j, k) local corner indices, or None if clipping fails."""
    n = len(pts3)
    if n < 3:
        return None
    if n == 3:
        return [(0, 1, 2)]
    poly = _project(pts3)
    area = _area2(poly)
    if abs(area) < eps:
        return None
    ccw = area > 0
    idx = list(range(n))
    tris = []
    guard = 0
    limit = n * n + 8
    while len(idx) > 3:
        guard += 1
        if guard > limit:
            return None
        found = False
        m = len(idx)
        for i in range(m):
            i0, i1, i2 = idx[(i - 1) % m], idx[i], idx[(i + 1) % m]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = _cross2(a, b, c)
            convex = (cr > eps) if ccw else (cr < -eps)
            if not convex:
                continue
            ear = True
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                if _point_in_tri(poly[j], a, b, c):
                    ear = False
                    break
            if ear:
                tris.append((i0, i1, i2))
                idx.pop(i)
                found = True
                break
        if not found:
            return None
    tris.append((idx[0], idx[1], idx[2]))
    return tris


def fan_tris(n):
    return [(0, i, i + 1) for i in range(1, n - 1)]


def parse_verts_and_lines(text):
    ends_nl = text.endswith("\n") or text.endswith("\r\n")
    parts = text.splitlines()
    verts = []
    for core in parts:
        stripped = core.strip()
        if stripped.startswith("v ") or stripped.startswith("v\t"):
            bits = stripped.split()
            if len(bits) < 4:
                continue
            verts.append(tuple(gst_read._obj_floats(bits[1:], 3, "vertex")))
    return verts, parts, ends_nl


def triangulate_face(tokens, verts):
    if len(tokens) < 3:
        raise SystemExit("face with fewer than 3 corners: f " + " ".join(tokens))
    if len(tokens) == 3:
        return ["f " + " ".join(tokens)], False
    pts = []
    ok = True
    for tok in tokens:
        try:
            i = _v_index(tok, len(verts))
        except (ValueError, SystemExit):
            ok = False
            break
        if i < 0 or i >= len(verts):
            ok = False
            break
        pts.append(verts[i])
    tris = ear_clip(pts) if ok else None
    fallback = False
    if tris is None:
        tris = fan_tris(len(tokens))
        fallback = True
    return ["f " + " ".join((tokens[i], tokens[j], tokens[k])) for i, j, k in tris], fallback


def triangulate_src(text):
    verts, parts, ends_nl = parse_verts_and_lines(text)
    out = []
    rec = {"faces": 0, "triangles_in": 0, "ngons": 0, "triangles_out": 0, "fan_fallback": 0}
    for core in parts:
        stripped = core.strip()
        if stripped.startswith("f ") or stripped.startswith("f\t"):
            tokens = stripped.split()[1:]
            rec["faces"] += 1
            if len(tokens) > 3:
                rec["ngons"] += 1
            else:
                rec["triangles_in"] += 1
            faces, fallback = triangulate_face(tokens, verts)
            if fallback and len(tokens) > 3:
                rec["fan_fallback"] += 1
            rec["triangles_out"] += len(faces)
            out.extend(faces)
        else:
            out.append(core)
    body = "\n".join(out)
    if ends_nl or parts:
        body += "\n"
    return body, rec


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Turn OBJ n-gon faces into triangles with ear-clipping (concave n-gons stay inside the polygon).")
    ap.add_argument("obj")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.obj, a.out, a.in_place)
    if a.json:
        safe_out.check(a.obj, a.json, a.in_place)
    src = open(a.obj, encoding="utf-8", errors="replace").read()
    if not any(ln.strip().startswith("v ") for ln in src.splitlines()):
        raise GstInputError("OBJ has no vertices")
    body, rec = triangulate_src(src)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(body)
    rec["out"] = a.out
    extra = f", {rec['fan_fallback']} fan fallback(s)" if rec["fan_fallback"] else ""
    print(f"{rec['faces']} face(s), {rec['ngons']} n-gon(s) -> {rec['triangles_out']} triangle(s){extra} -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
