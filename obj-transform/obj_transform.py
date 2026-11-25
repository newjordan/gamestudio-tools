#!/usr/bin/env python3
"""obj-transform: scale, flip, and/or rotate an OBJ by 90/180/270 degrees around an axis.
Vertex and vertex-normal lines are rewritten; faces, UVs, `mtllib`, `usemtl`, groups and
smoothing lines are copied through. Writes a new OBJ; the input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, math, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def parse_scale(s):
    if s is None:
        return (1.0, 1.0, 1.0)
    parts = [float(x) for x in s.split(",")]
    if len(parts) == 1:
        return (parts[0], parts[0], parts[0])
    if len(parts) == 3:
        return tuple(parts)
    raise SystemExit("--scale must be S or SX,SY,SZ")


def rot90(x, y, z, axis, turns):
    """turns is 1,2,3 for 90,180,270 (right-hand, counterclockwise looking along +axis? 
    We use right-hand rule: positive rotation about the named axis)."""
    turns %= 4
    for _ in range(turns):
        if axis == "x":
            y, z = -z, y
        elif axis == "y":
            x, z = z, -x
        else:  # z
            x, y = -y, x
    return x, y, z


def apply(x, y, z, scale, flips, axis, turns, is_normal=False):
    if not is_normal:
        x, y, z = x * scale[0], y * scale[1], z * scale[2]
    else:
        # normals: divide by scale (inverse-transpose of diag scale), then normalize later
        x, y, z = x / (scale[0] or 1), y / (scale[1] or 1), z / (scale[2] or 1)
    for f in flips:
        if f == "x":
            x = -x
        elif f == "y":
            y = -y
        else:
            z = -z
    if turns:
        x, y, z = rot90(x, y, z, axis, turns)
    if is_normal:
        n = math.sqrt(x * x + y * y + z * z) or 1.0
        x, y, z = x / n, y / n, z / n
    return x, y, z


def fmt(n):
    s = f"{n:.9g}"
    return s


def transform_src(text, scale, flips, axis, turns):
    out, n_v, n_vn = [], 0, 0
    ends_nl = text.endswith("\n") or text.endswith("\r\n")
    for core in text.splitlines():
        stripped = core.strip()
        if stripped.startswith("v ") and not stripped.startswith("vt ") and not stripped.startswith("vn "):
            parts = stripped.split()
            nums = [float(p) for p in parts[1:4]]
            w = parts[4:] 
            x, y, z = apply(nums[0], nums[1], nums[2], scale, flips, axis, turns, False)
            line = "v " + " ".join(fmt(v) for v in (x, y, z) + tuple())
            if w:
                line += " " + " ".join(w)
            out.append(line)
            n_v += 1
        elif stripped.startswith("vn "):
            parts = stripped.split()
            nums = [float(p) for p in parts[1:4]]
            x, y, z = apply(nums[0], nums[1], nums[2], scale, flips, axis, turns, True)
            out.append("vn " + " ".join(fmt(v) for v in (x, y, z)))
            n_vn += 1
        else:
            out.append(core)
    body = "\n".join(out)
    if ends_nl or out:
        body += "\n"
    return body, n_v, n_vn


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scale, flip, or rotate-90 an OBJ.")
    ap.add_argument("obj")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--scale", help="S or SX,SY,SZ (default: 1)")
    ap.add_argument("--flip", action="append", default=[], choices=("x", "y", "z"),
                    help="flip an axis (repeatable)")
    ap.add_argument("--rotate", type=int, default=0, choices=(0, 90, 180, 270),
                    help="rotation in degrees (right-hand about --axis)")
    ap.add_argument("--axis", default="y", choices=("x", "y", "z"))
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.obj, a.out, a.in_place)
    if a.json:
        safe_out.check(a.obj, a.json, a.in_place)
    scale = parse_scale(a.scale)
    turns = {0: 0, 90: 1, 180: 2, 270: 3}[a.rotate]
    if scale == (1.0, 1.0, 1.0) and not a.flip and not turns:
        sys.exit("nothing to do: pass --scale, --flip and/or --rotate")
    body, n_v, n_vn = transform_src(open(a.obj, encoding="utf-8", errors="replace").read(),
                                    scale, a.flip, a.axis, turns)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(body)
    rec = {"vertices": n_v, "normals": n_vn, "scale": list(scale), "flip": a.flip,
           "rotate": a.rotate, "axis": a.axis, "out": a.out}
    print(f"{n_v} vertex/vertices, {n_vn} normal(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
