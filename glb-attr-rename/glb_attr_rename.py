#!/usr/bin/env python3
"""glb-attr-rename: rename vertex attributes on a static binary GLB
(`--map OLD=NEW,...` or `--pattern` / `--replace`). POSITION cannot be renamed.
Colliding destination names are refused. Attribute accessors are left in place
(the binary is not rebuilt). Animated, skinned or morphed files are refused.
The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
import safe_out, glb_lod  # noqa: E402


def parse_map(s):
    out = {}
    if not s:
        return out
    # JSON object or comma old=new
    p = s.strip()
    if p.startswith("{"):
        data = json.loads(p)
        if not isinstance(data, dict):
            raise SystemExit("--map JSON must be an object")
        return {str(k): str(v) for k, v in data.items()}
    for part in p.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"bad --map entry {part!r} (expected old=new)")
        old, new = part.split("=", 1)
        old, new = old.strip(), new.strip()
        if not old or not new:
            raise SystemExit(f"bad --map entry {part!r}")
        out[old] = new
    return out


def apply_name(old, mapping, pattern, repl):
    if old in mapping:
        return mapping[old]
    if pattern is not None:
        return pattern.sub(repl, old)
    return old


def rename(path, out_path, mapping, pattern, repl):
    gltf, bin_ = glb_lod.load_glb(path)
    if gltf.get("animations") or gltf.get("skins"):
        raise SystemExit("animated/skinned files are not supported")
    renamed = 0
    for m in gltf.get("meshes") or []:
        for p in m.get("primitives") or []:
            if p.get("targets"):
                raise SystemExit("morph targets are not supported")
            attrs = dict(p.get("attributes") or {})
            new_attrs = {}
            planned = {}
            for k in attrs:
                nk = apply_name(k, mapping, pattern, repl)
                if k == "POSITION" and nk != "POSITION":
                    raise SystemExit("POSITION cannot be renamed")
                planned[k] = nk
            # collisions: two olds -> same new, or new already exists and isn't the same key leaving
            destinations = {}
            for k, nk in planned.items():
                if nk in destinations and destinations[nk] != k:
                    raise SystemExit(f"attribute name collision: {k} and {destinations[nk]} both become {nk}")
                destinations[nk] = k
            occupied = set(attrs)
            for k, nk in planned.items():
                if nk != k and nk in occupied and planned.get(nk) == nk:
                    raise SystemExit(f"cannot rename {k} to {nk}: that attribute already exists")
            for k, ai in attrs.items():
                nk = planned[k]
                if nk != k:
                    renamed += 1
                if nk in new_attrs:
                    raise SystemExit(f"attribute name collision on {nk}")
                new_attrs[nk] = ai
            if "POSITION" not in new_attrs:
                raise SystemExit("primitive would have no POSITION after rename")
            p["attributes"] = new_attrs
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    glb_lod.save_glb(out_path, gltf, bin_)
    return {"out": out_path, "renamed": renamed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rename vertex attributes on a static GLB.")
    ap.add_argument("input", help=".glb")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--map", default="", help="old=new,old=new or a JSON object")
    ap.add_argument("--pattern", help="regex against the current attribute name")
    ap.add_argument("--replace", default="", help="replacement for --pattern (backrefs allowed)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if os.path.splitext(a.input)[1].lower() != ".glb":
        raise SystemExit("glb-attr-rename needs a binary .glb")
    if not a.map and not a.pattern:
        raise SystemExit("pass --map and/or --pattern")
    if a.pattern and a.replace is None:
        raise SystemExit("--pattern needs --replace")
    pat = re.compile(a.pattern) if a.pattern else None
    mapping = parse_map(a.map)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    rec = rename(a.input, a.out, mapping, pat, a.replace or "")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("renamed %d attribute(s) -> %s" % (rec["renamed"], a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
