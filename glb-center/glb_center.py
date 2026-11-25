#!/usr/bin/env python3
"""glb-center: move a glTF/GLB scene so its world-space AABB sits on a chosen
pivot (bbox centre by default, or feet / min corner / a point). The glTF-only
counterpart of obj-recenter; the shift is applied to each scene root node, same
as mesh-pivot-fix, and leaves vertex data and child animations untouched (warns
when a skin or a root translation animation may override it). The input is never
overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import safe_out, mesh_pivot_fix  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Center a glTF/GLB scene on its AABB (or feet / min / a point).")
    ap.add_argument("input", help=".glb or .gltf")
    ap.add_argument("-o", "--out", help="output path (required unless --report)")
    ap.add_argument("--mode", choices=["center", "bottom", "min", "point"], default="center")
    ap.add_argument("--point", help="x,y,z for --mode point (world space, before the shift)")
    ap.add_argument("--report", action="store_true", help="only print the bounds, write nothing")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    ext = os.path.splitext(a.input)[1].lower()
    if ext not in (".glb", ".gltf"):
        sys.exit("unsupported file type (use .glb or .gltf; for OBJ use obj-recenter)")
    off = [float(x) for x in a.point.split(",")] if a.point else None
    if a.mode == "point" and (off is None or len(off) != 3):
        sys.exit("--mode point needs --point x,y,z")
    if not a.report and not a.out:
        sys.exit("pass -o or --report")
    if a.out:
        safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    js, chunks, ver = mesh_pivot_fix.read_glb(a.input)
    if a.report:
        lo, hi = mesh_pivot_fix.world_bounds(js)
        rec = {"min": lo.tolist(), "max": hi.tolist()}
        print(f"bounds min {mesh_pivot_fix.fmt(lo)} max {mesh_pivot_fix.fmt(hi)}")
        if a.json:
            json.dump(rec, open(a.json, "w"), indent=2)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    r = mesh_pivot_fix.fix_gltf(js, a.mode, off)
    if chunks is None:
        json.dump(js, open(a.out, "w"), indent=1)
    else:
        mesh_pivot_fix.write_glb(a.out, js, chunks, ver)
    r["out"] = a.out
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({k: v for k, v in r.items()}, open(a.json, "w"), indent=2)
    print(f"before: min {mesh_pivot_fix.fmt(r['before']['min'])} max {mesh_pivot_fix.fmt(r['before']['max'])}\n"
          f"after:  min {mesh_pivot_fix.fmt(r['after']['min'])} max {mesh_pivot_fix.fmt(r['after']['max'])}\n"
          f"shift {mesh_pivot_fix.fmt(r['shift'])} -> {a.out}")
    for w in r["warnings"]:
        print("WARN " + w)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
