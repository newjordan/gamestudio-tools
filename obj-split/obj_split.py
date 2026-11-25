#!/usr/bin/env python3
"""obj-split: split an OBJ into one file per `g` / `o` group (or only groups, or only
objects), remapping `v` / `vt` / `vn` indices so each file is self-contained. Material
(`mtllib`, `usemtl`), smoothing (`s`) and comment lines that belong to a group travel
with it; the file prelude (typically `mtllib`) is copied onto every output. Writes
under `--outdir`. The input is never overwritten unless `--in-place`.
"""
import argparse, os, json, re, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, obj_weld  # noqa: E402


def safe_name(s, fallback="part"):
    s = (s or "").strip() or fallback
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("._") or fallback
    return s


def parse_name(line, kind):
    s = line.strip()
    if s.startswith(kind + " "):
        return s[len(kind) + 1:].strip() or "default"
    return None


def extract_go(prelude):
    """Pull leading g/o names out of the pre-vertex prelude so they are not copied onto every part."""
    g, o, rest = "default", "default", []
    for raw in prelude or []:
        s = raw.strip()
        if s.startswith("g "):
            g = s[2:].strip() or "default"
        elif s.startswith("o "):
            o = s[2:].strip() or "default"
        else:
            rest.append(raw)
    return g, o, rest


def split_cmds(cmds, by, cur_g="default", cur_o="default"):
    """Yield (label, cmds_for_group) in file order. `by` is 'g', 'o', or 'both'."""
    buckets = []  # (label, cmds)
    current = None
    prelude_raw = []  # raw lines after verts start but before first face, still tagged

    def label():
        if by == "g":
            return cur_g
        if by == "o":
            return cur_o
        # both: prefer a non-default object name, else group, and change on either
        if cur_o != "default":
            return f"{cur_g}_{cur_o}" if cur_g != "default" and cur_g != cur_o else cur_o
        return cur_g

    def start_part():
        nonlocal current
        lab = label()
        current = []
        if by in ("g", "both") and cur_g != "default":
            current.append(("raw", f"g {cur_g}"))
        if by in ("o", "both") and cur_o != "default":
            current.append(("raw", f"o {cur_o}"))
        buckets.append((lab, current))

    started = False
    for kind, payload in cmds:
        if kind == "raw":
            g = parse_name(payload, "g")
            o = parse_name(payload, "o")
            changed = False
            if g is not None and by in ("g", "both"):
                cur_g = g
                changed = True
            if o is not None and by in ("o", "both"):
                cur_o = o
                changed = True
            if g is not None and by == "o":
                cur_g = g  # still record, but don't split
            if o is not None and by == "g":
                cur_o = o
            if changed:
                start_part()
                # start_part already wrote the g/o header; skip re-appending that line
                continue
            if current is None:
                prelude_raw.append((kind, payload))
            else:
                current.append((kind, payload))
            continue
        # faces / lines
        if current is None:
            start_part()
            current.extend(prelude_raw)
            prelude_raw = []
        current.append((kind, payload))
    # drop empty (no faces/lines) parts
    out = []
    for lab, part in buckets:
        if any(k in ("f", "l") for k, _ in part):
            out.append((lab, part))
    return out


def remap_part(v, vt, vn, cmds):
    used_v, used_vt, used_vn = set(), set(), set()
    for kind, payload in cmds:
        if kind not in ("f", "l"):
            continue
        for vi, vti, vni in payload:
            used_v.add(vi)
            if vti is not None: used_vt.add(vti)
            if vni is not None: used_vn.add(vni)
    v_map = {i: n for n, i in enumerate(sorted(used_v))}
    vt_map = {i: n for n, i in enumerate(sorted(used_vt))}
    vn_map = {i: n for n, i in enumerate(sorted(used_vn))}
    new_v = [v[i] for i in sorted(used_v)]
    new_vt = [vt[i] for i in sorted(used_vt)]
    new_vn = [vn[i] for i in sorted(used_vn)]
    new_cmds = []
    for kind, payload in cmds:
        if kind in ("f", "l"):
            corners = []
            for vi, vti, vni in payload:
                corners.append((
                    v_map[vi],
                    vt_map[vti] if vti is not None else None,
                    vn_map[vni] if vni is not None else None,
                ))
            new_cmds.append((kind, corners))
        else:
            new_cmds.append((kind, payload))
    return np.array(new_v, float) if new_v else np.zeros((0, 3)), new_vt, new_vn, new_cmds


def unique_path(outdir, stem, used):
    name = stem
    i = 2
    while name.lower() in used:
        name = f"{stem}_{i}"
        i += 1
    used.add(name.lower())
    return os.path.join(outdir, name + ".obj")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split an OBJ into one file per g/o group, remapping indices.")
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--by", choices=("g", "o", "both"), default="both",
                    help="split on group lines, object lines, or either (default: both)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    sources = [a.input]
    safe_out.check(a.input, a.outdir, a.in_place)  # only if someone points outdir at the file
    if a.json:
        safe_out.check_any(sources, a.json, a.in_place)
    v, vt, vn, cmds, prelude = obj_weld.load_obj(a.input)
    v = v.tolist() if hasattr(v, "tolist") else list(v)
    cur_g, cur_o, prelude = extract_go(prelude)
    parts = split_cmds(cmds, a.by, cur_g, cur_o)
    if not parts:
        sys.exit("no groups with faces or lines to split")
    os.makedirs(a.outdir, exist_ok=True)
    used, recs = set(), []
    for lab, part in parts:
        dest = unique_path(a.outdir, safe_name(lab), used)
        if os.path.abspath(dest) == os.path.abspath(a.input) and not a.in_place:
            sys.exit(f"refusing to overwrite the input; pick a different output path or pass --in-place: {dest}")
        nv, nvt, nvn, ncmds = remap_part(v, vt, vn, part)
        obj_weld.write_obj(dest, nv, nvt, nvn, ncmds, prelude)
        recs.append({"name": lab, "out": dest, "vertices": len(nv),
                     "faces": sum(1 for k, _ in ncmds if k == "f")})
    rec = {"parts": recs, "count": len(recs), "by": a.by, "outdir": a.outdir}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{len(recs)} part(s) -> {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
