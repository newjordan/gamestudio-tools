#!/usr/bin/env python3
"""obj-merge: concatenate several OBJ files into one, remapping `v` / `vt` / `vn` indices
and keeping groups. Each file is prefixed with `g <stem>` / `o <stem>`, and existing
`g` / `o` names are prefixed with that stem so groups stay unique. Material (`mtllib`,
`usemtl`), smoothing (`s`) and comment lines are kept in order relative to the faces
they prefix. Writes a new OBJ; an input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402
from gst_errors import GstInputError  # noqa: E402


def stem_of(path):
    return os.path.splitext(os.path.basename(path))[0]


def prefix_raw(line, stem):
    s = line.strip()
    if s.startswith("g "):
        rest = s[2:].strip() or "default"
        return f"g {stem}_{rest}"
    if s.startswith("o "):
        rest = s[2:].strip() or "default"
        return f"o {stem}_{rest}"
    return line


def merge_objs(paths):
    all_v, all_vt, all_vn, all_cmds, prelude = [], [], [], [], []
    files = []
    for i, path in enumerate(paths):
        v, vt, vn, cmds, pre = obj_weld.load_obj(path)
        if len(v) == 0:
            raise GstInputError("OBJ has no vertices")
        v = v.tolist() if hasattr(v, "tolist") else list(v)
        vt = [list(t) for t in vt]
        vn = [list(n) for n in vn]
        stem = stem_of(path)
        vo, vto, vno = len(all_v), len(all_vt), len(all_vn)
        if i == 0:
            prelude = list(pre)
        else:
            for line in pre:
                all_cmds.append(("raw", line))
        all_cmds.append(("raw", f"o {stem}"))
        all_cmds.append(("raw", f"g {stem}"))
        n_faces = 0
        for kind, payload in cmds:
            if kind in ("f", "l"):
                if kind == "f":
                    n_faces += 1
                remapped = []
                for vi, vti, vni in payload:
                    remapped.append((
                        (vi + vo) if vi is not None else None,
                        (vti + vto) if vti is not None else None,
                        (vni + vno) if vni is not None else None,
                    ))
                all_cmds.append((kind, remapped))
            elif kind == "raw":
                all_cmds.append(("raw", prefix_raw(payload, stem)))
            else:
                all_cmds.append((kind, payload))
        all_v.extend(v)
        all_vt.extend(vt)
        all_vn.extend(vn)
        files.append({"path": path, "stem": stem, "vertices": len(v), "faces": n_faces})
    rec = {"files": files, "vertices": len(all_v), "uvs": len(all_vt), "normals": len(all_vn),
           "faces": sum(f["faces"] for f in files)}
    return (np.array(all_v, float) if all_v else np.zeros((0, 3)),
            all_vt, all_vn, all_cmds, prelude, rec)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge several OBJ files, remapping vertex / UV / normal indices.")
    ap.add_argument("objs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if len(a.objs) < 2:
        sys.exit("pass at least two OBJ files")
    safe_out.check_any(a.objs, a.out, a.in_place)
    if a.json:
        safe_out.check_any(a.objs, a.json, a.in_place)
    v, vt, vn, cmds, prelude, rec = merge_objs(a.objs)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    obj_weld.write_obj(a.out, v, vt, vn, cmds, prelude)
    rec["out"] = a.out
    print(f"{len(a.objs)} file(s), {rec['vertices']} vert(s), {rec['faces']} face(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
