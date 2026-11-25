#!/usr/bin/env python3
"""glb-quantize: snap float POSITION, NORMAL and TEXCOORD accessors in a static
GLB to a grid (`--digits` decimal places, or `--step`). Normals are renormalised
afterwards. The first vertex in a cell is not merged (that is glb-weld). Animated,
skinned, morphed or sparse-accessor files are refused. The input is never
overwritten unless `--in-place`.
"""
import argparse, os, copy, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
import safe_out, glb_lod  # noqa: E402


def snap(arr, step):
    return np.round(arr / step) * step


def quantize(path, out_path, step, uv_step):
    gltf, bin_ = glb_lod.load_glb(path)
    if gltf.get("animations") or gltf.get("skins"):
        raise SystemExit("animated/skinned files are not supported")
    new = copy.deepcopy(gltf)
    chunks, views, accs = [], [], []

    def add_view(data, target=None):
        pad = -sum(len(c) for c in chunks) % 4
        if pad:
            chunks.append(b"\0" * pad)
        off = sum(len(c) for c in chunks)
        chunks.append(data)
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            v["target"] = target
        views.append(v)
        return len(views) - 1

    for img in new.get("images", []):
        if "bufferView" in img:
            bv = gltf["bufferViews"][img["bufferView"]]
            o = bv.get("byteOffset", 0)
            img["bufferView"] = add_view(bin_[o:o + bv["byteLength"]])
    n_acc = 0
    typ = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}
    for m in new.get("meshes", []):
        for p in m["primitives"]:
            if p.get("mode", 4) != 4:
                raise SystemExit("only triangle-list primitives are supported")
            if p.get("targets"):
                raise SystemExit("morph targets are not supported")
            attrs = {}
            for k, ai in p["attributes"].items():
                acc = gltf["accessors"][ai]
                if acc["componentType"] != 5126:
                    raise SystemExit(f"attribute {k} is not float32 (unsupported)")
                attrs[k] = glb_lod.read_acc(gltf, bin_, ai).astype(np.float64)
            if "POSITION" in attrs:
                attrs["POSITION"] = snap(attrs["POSITION"], step)
            if "NORMAL" in attrs:
                n = snap(attrs["NORMAL"], step)
                lens = np.linalg.norm(n, axis=1, keepdims=True)
                lens[lens == 0] = 1.0
                attrs["NORMAL"] = n / lens
            for k in list(attrs):
                if k.startswith("TEXCOORD"):
                    attrs[k] = snap(attrs[k], uv_step)
            # indices copied through
            idx = None
            if "indices" in p:
                idx = glb_lod.read_acc(gltf, bin_, p["indices"]).reshape(-1)
            p["attributes"] = {}
            for k, arr in attrs.items():
                arr = np.ascontiguousarray(arr, dtype="<f4")
                if arr.ndim == 1:
                    arr = arr.reshape(-1, 1)
                vi = add_view(arr.tobytes(), 34962)
                a = {"bufferView": vi, "componentType": 5126, "count": len(arr), "type": typ[arr.shape[1]]}
                if k == "POSITION":
                    a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
                accs.append(a)
                p["attributes"][k] = len(accs) - 1
                n_acc += 1
            if idx is not None:
                ct, dt = (5123, "<u2") if int(idx.max(initial=0)) < 65536 else (5125, "<u4")
                vi = add_view(np.ascontiguousarray(idx, dtype=dt).tobytes(), 34963)
                accs.append({"bufferView": vi, "componentType": ct, "count": len(idx), "type": "SCALAR"})
                p["indices"] = len(accs) - 1
    new["bufferViews"], new["accessors"] = views, accs
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    glb_lod.save_glb(out_path, new, b"".join(chunks))
    return {"out": out_path, "step": step, "uv_step": uv_step, "accessors": n_acc}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Snap glTF POSITION/NORMAL/TEXCOORD floats to a grid.")
    ap.add_argument("input", help=".glb")
    ap.add_argument("-o", "--out", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--digits", type=int, default=None, help="decimal places for positions/normals (default: 4)")
    g.add_argument("--step", type=float, default=None, help="grid step for positions/normals")
    ap.add_argument("--uv-digits", type=int, default=None, help="decimal places for UVs (default: same as --digits or 5)")
    ap.add_argument("--uv-step", type=float, default=None, help="grid step for UVs")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    ext = os.path.splitext(a.input)[1].lower()
    if ext != ".glb":
        sys.exit("glb-quantize needs a binary .glb")
    if a.step is not None:
        if a.step <= 0:
            sys.exit("--step must be > 0")
        step = a.step
    else:
        digits = 4 if a.digits is None else a.digits
        if digits < 0:
            sys.exit("--digits must be >= 0")
        step = 10 ** (-digits)
    if a.uv_step is not None:
        if a.uv_step <= 0:
            sys.exit("--uv-step must be > 0")
        uv_step = a.uv_step
    elif a.uv_digits is not None:
        if a.uv_digits < 0:
            sys.exit("--uv-digits must be >= 0")
        uv_step = 10 ** (-a.uv_digits)
    else:
        uv_step = 10 ** (-(a.digits if a.digits is not None else 5))
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    rec = quantize(a.input, a.out, step, uv_step)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"quantized {rec['accessors']} accessor(s) step={step:g} uv_step={uv_step:g} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
