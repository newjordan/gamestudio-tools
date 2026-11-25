#!/usr/bin/env python3
"""glb-weld: weld nearby vertices in a static GLB (the glTF counterpart of
obj-weld). Vertices whose positions quantise to the same `--epsilon` cell are
merged; optional `--also-uv` / `--also-normal` add TEXCOORD_0 / NORMAL to the
key so seams stay split. Degenerate triangles are dropped. Animated, skinned,
morphed or sparse-accessor files are refused. The input is never overwritten
unless `--in-place`.
"""
import argparse, os, copy, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "obj-weld"))
import safe_out, glb_lod, obj_weld  # noqa: E402


def weld_prim(attrs, idx, eps, also_uv, also_normal):
    pos = attrs["POSITION"].astype(np.float64)
    uv = attrs.get("TEXCOORD_0")
    nrm = attrs.get("NORMAL")
    key_of = []
    for i in range(len(pos)):
        extra = []
        if also_uv and uv is not None:
            extra.extend(obj_weld.quant_key(uv[i], eps))
        if also_normal and nrm is not None:
            extra.extend(obj_weld.quant_key(nrm[i], 1e-3 if eps < 1e-3 else eps))
        key_of.append(obj_weld.quant_key(pos[i], eps, tuple(extra)))
    first, remap = {}, {}
    keep = []
    for i, key in enumerate(key_of):
        if key not in first:
            first[key] = len(keep)
            keep.append(i)
        remap[i] = first[key]
    keep = np.array(keep, np.int64)
    new_attrs = {k: v[keep] for k, v in attrs.items()}
    mapped = np.array([remap[int(i)] for i in idx], np.int64)
    tris = mapped.reshape(-1, 3)
    ok = (tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 0] != tris[:, 2])
    return new_attrs, tris[ok].reshape(-1), int(len(pos)), int(len(keep)), int(len(idx) // 3), int(ok.sum())


def weld(path, out_path, eps, also_uv, also_normal):
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
    v_in = v_out = t_in = t_out = 0
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
                attrs[k] = glb_lod.read_acc(gltf, bin_, ai)
            if "POSITION" not in attrs:
                raise SystemExit("primitive has no POSITION")
            idx = (glb_lod.read_acc(gltf, bin_, p["indices"]).reshape(-1).astype(np.int64)
                   if "indices" in p else np.arange(len(attrs["POSITION"])))
            idx = glb_lod.require_indices(idx, len(attrs["POSITION"]))
            nattrs, nidx, bi, ai, bt, at = weld_prim(attrs, idx, eps, also_uv, also_normal)
            v_in += bi; v_out += ai; t_in += bt; t_out += at
            p["attributes"] = {}
            typ = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}
            for k, arr in nattrs.items():
                arr = np.ascontiguousarray(arr, dtype="<f4")
                if arr.ndim == 1:
                    arr = arr.reshape(-1, 1)
                vi = add_view(arr.tobytes(), 34962)
                a = {"bufferView": vi, "componentType": 5126, "count": len(arr), "type": typ[arr.shape[1]]}
                if k == "POSITION":
                    a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
                accs.append(a)
                p["attributes"][k] = len(accs) - 1
            ct, dt = (5123, "<u2") if len(nattrs["POSITION"]) < 65536 else (5125, "<u4")
            vi = add_view(np.ascontiguousarray(nidx, dtype=dt).tobytes(), 34963)
            accs.append({"bufferView": vi, "componentType": ct, "count": len(nidx), "type": "SCALAR"})
            p["indices"] = len(accs) - 1
    new["bufferViews"], new["accessors"] = views, accs
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    glb_lod.save_glb(out_path, new, b"".join(chunks))
    return {"out": out_path, "vertices_before": v_in, "vertices_after": v_out,
            "triangles_before": t_in, "triangles_after": t_out, "epsilon": eps}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Weld nearby vertices in a static GLB.")
    ap.add_argument("input", help=".glb")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--epsilon", type=float, default=1e-5)
    ap.add_argument("--also-uv", action="store_true", help="do not weld across a UV seam")
    ap.add_argument("--also-normal", action="store_true", help="do not weld across a normal seam")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.epsilon <= 0:
        sys.exit("--epsilon must be positive")
    ext = os.path.splitext(a.input)[1].lower()
    if ext != ".glb":
        sys.exit("glb-weld needs a binary .glb (convert with obj-to-glb, or use obj-weld on an OBJ)")
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    rec = weld(a.input, a.out, a.epsilon, a.also_uv, a.also_normal)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{rec['vertices_before']} -> {rec['vertices_after']} vert(s), "
          f"{rec['triangles_before']} -> {rec['triangles_after']} triangle(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
