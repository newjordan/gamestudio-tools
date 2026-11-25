#!/usr/bin/env python3
"""glb-attr-drop: drop named vertex attributes from a static GLB (NORMAL,
TEXCOORD_0, COLOR_0, TANGENT, …). POSITION cannot be dropped. The file is
rebuilt from the remaining float attributes, indices, and images. Animated,
skinned, morphed or sparse-accessor files are refused. The input is never
overwritten unless `--in-place`.
"""
import argparse, os, copy, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
import safe_out, glb_lod  # noqa: E402


def parse_names(s):
    names = [n.strip() for n in s.replace(" ", ",").split(",") if n.strip()]
    if not names:
        raise SystemExit("no attribute names to drop")
    if any(n.upper() == "POSITION" or n == "POSITION" for n in names):
        raise SystemExit("POSITION cannot be dropped")
    return names


def drop(path, out_path, names):
    gltf, bin_ = glb_lod.load_glb(path)
    if gltf.get("animations") or gltf.get("skins"):
        raise SystemExit("animated/skinned files are not supported")
    drop_set = set(names)
    new = copy.deepcopy(gltf)
    chunks, views, accs = [], [], []
    dropped = 0

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

    typ = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}
    for img in new.get("images", []):
        if "bufferView" in img:
            bv = gltf["bufferViews"][img["bufferView"]]
            o = bv.get("byteOffset", 0)
            img["bufferView"] = add_view(bin_[o:o + bv["byteLength"]])
    for m in new.get("meshes", []):
        for p in m["primitives"]:
            if p.get("mode", 4) != 4:
                raise SystemExit("only triangle-list primitives are supported")
            if p.get("targets"):
                raise SystemExit("morph targets are not supported")
            attrs = {}
            for k, ai in list(p["attributes"].items()):
                if k in drop_set:
                    dropped += 1
                    continue
                acc = gltf["accessors"][ai]
                if acc["componentType"] != 5126:
                    raise SystemExit(f"attribute {k} is not float32 (unsupported)")
                attrs[k] = glb_lod.read_acc(gltf, bin_, ai).astype(np.float64)
            if "POSITION" not in attrs:
                raise SystemExit("primitive has no POSITION after drop")
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
            if idx is not None:
                ct, dt = (5123, "<u2") if int(idx.max(initial=0)) < 65536 else (5125, "<u4")
                vi = add_view(np.ascontiguousarray(idx, dtype=dt).tobytes(), 34963)
                accs.append({"bufferView": vi, "componentType": ct, "count": len(idx), "type": "SCALAR"})
                p["indices"] = len(accs) - 1
    new["bufferViews"], new["accessors"] = views, accs
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    glb_lod.save_glb(out_path, new, b"".join(chunks))
    return {"out": out_path, "dropped": dropped, "names": names}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Drop named vertex attributes from a static GLB.")
    ap.add_argument("input", help=".glb")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--drop", required=True, help="comma-separated accessor names (NORMAL, TEXCOORD_0, …)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if os.path.splitext(a.input)[1].lower() != ".glb":
        sys.exit("glb-attr-drop needs a binary .glb")
    names = parse_names(a.drop)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    rec = drop(a.input, a.out, names)
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"dropped {rec['dropped']} attribute(s) {names} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
