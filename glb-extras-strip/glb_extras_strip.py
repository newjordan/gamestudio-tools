#!/usr/bin/env python3
"""glb-extras-strip: remove every `extras` object from a glTF JSON document
(binary .glb or .gltf). The binary buffer is left in place; the file is not
rebuilt beyond rewriting the JSON chunk. Animated, skinned and morphed files
are allowed. The input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, sys, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
import safe_out, glb_lod  # noqa: E402


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def strip_extras(node):
    """Return (cleaned, count of extras keys removed)."""
    if isinstance(node, dict):
        n = 0
        out = {}
        for k, v in node.items():
            if k == "extras":
                n += 1
                continue
            nv, c = strip_extras(v)
            out[k] = nv
            n += c
        return out, n
    if isinstance(node, list):
        n = 0
        out = []
        for v in node:
            nv, c = strip_extras(v)
            out.append(nv)
            n += c
        return out, n
    return node, 0


def load_any(path):
    low = path.lower()
    if low.endswith(".glb"):
        gltf, bin_ = gst_read.load_glb(path)
        return "glb", gltf, bin_
    if low.endswith(".gltf"):
        js, bin_, _ver, _ch = gst_read.load_gltf_or_glb(path)
        return "gltf", js, bin_
    raise GstInputError("glb-extras-strip expects a .glb or .gltf file")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Strip extras from a GLB or glTF file.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)

    kind, gltf, bin_ = load_any(a.input)
    cleaned, dropped = strip_extras(gltf)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    if kind == "glb":
        glb_lod.save_glb(a.out, cleaned, bin_ or b"")
    else:
        json.dump(cleaned, open(a.out, "w"), indent=2)
    rec = {"out": a.out, "kind": kind, "dropped": dropped}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("stripped %d extras -> %s" % (dropped, a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
