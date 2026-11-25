#!/usr/bin/env python3
"""obj-to-glb: convert Wavefront .obj (+ .mtl) to a single binary .glb.

Handles v/vt/vn, negative indices, n-gon fan triangulation, usemtl groups (one primitive per material),
.mtl Kd colour and map_Kd (embedded as PNG), flat normals when the OBJ has none, V-flip for glTF UVs,
--scale and --up-axis z. Vertices are deduplicated by (position, uv, normal). Static meshes only.
Written from the Wavefront OBJ / MTL conventions and the Khronos glTF 2.0 spec; no third-party code.
"""
import argparse, io, json, os, struct
import numpy as np
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def parse_mtl(path):
    mats, cur = {}, None
    if not os.path.exists(path):
        return mats
    for line in open(path, encoding="utf-8", errors="ignore"):
        p = line.split()
        if not p or p[0].startswith("#"):
            continue
        if p[0] == "newmtl":
            cur = mats.setdefault(" ".join(p[1:]), {})
        elif cur is not None and p[0] == "Kd" and len(p) >= 4:
            cur["kd"] = [float(v) for v in p[1:4]]
        elif cur is not None and p[0] == "d" and len(p) >= 2:
            cur["d"] = float(p[1])
        elif cur is not None and p[0] == "map_Kd":
            cur["map_kd"] = line.split(None, 1)[1].strip().split()[-1]
    return mats


def parse_obj(path):
    V, VT, VN, groups, mtllib, cur = [], [], [], {}, None, "default"
    for line in open(path, encoding="utf-8", errors="ignore"):
        p = line.split()
        if not p or p[0].startswith("#"):
            continue
        t = p[0]
        if t == "v":
            V.append(gst_read._obj_floats(p[1:], 3, "vertex"))
        elif t == "vt":
            VT.append(gst_read._obj_floats(p[1:], 2, "UV"))
        elif t == "vn":
            VN.append(gst_read._obj_floats(p[1:], 3, "normal"))
        elif t == "mtllib": mtllib = " ".join(p[1:])
        elif t == "usemtl": cur = " ".join(p[1:])
        elif t == "f":
            face = []
            for tok in p[1:]:
                a = (tok.split("/") + ["", ""])[:3]
                def ix(s, n, what="vertex"):
                    if not s: return None
                    try:
                        i = int(s)
                    except ValueError as e:
                        raise GstInputError("OBJ face has an invalid %s index" % what) from e
                    return i - 1 if i > 0 else n + i
                face.append((ix(a[0], len(V)), ix(a[1], len(VT)), ix(a[2], len(VN))))
            groups.setdefault(cur, []).append(face)
    nv, nvt, nvn = len(V), len(VT), len(VN)
    for faces in groups.values():
        for face in faces:
            if len(face) < 3:
                raise GstInputError("OBJ face has too few corners")
            for vi, ti, ni in face:
                if vi is None or vi < 0 or vi >= nv:
                    raise GstInputError("OBJ face vertex index is out of range")
                if ti is not None and (ti < 0 or ti >= nvt):
                    raise GstInputError("OBJ face UV index is out of range")
                if ni is not None and (ni < 0 or ni >= nvn):
                    raise GstInputError("OBJ face normal index is out of range")
    try:
        return (np.array(V, np.float32) if V else np.zeros((0, 3), np.float32),
                np.array(VT, np.float32) if VT else np.zeros((0, 2), np.float32),
                np.array(VN, np.float32) if VN else np.zeros((0, 3), np.float32),
                groups, mtllib)
    except ValueError as e:
        raise GstInputError("OBJ vertex data has inconsistent sizes") from e


def build_prim(V, VT, VN, faces):
    pos, uv, nor, idx, cache = [], [], [], [], {}
    for face in faces:
        for k in range(1, len(face) - 1):
            tri = [face[0], face[k], face[k + 1]]
            flat = None
            if any(c[2] is None for c in tri):
                a, b, c = (V[t[0]] for t in tri)
                n = np.cross(b - a, c - a)
                l = np.linalg.norm(n)
                flat = n / l if l else np.array([0, 1, 0], np.float32)
            for (vi, ti, ni) in tri:
                key = (vi, ti, ni) if ni is not None else (vi, ti, tuple(np.round(flat, 5)))
                if key not in cache:
                    cache[key] = len(pos)
                    pos.append(V[vi])
                    uv.append([VT[ti][0], 1 - VT[ti][1]] if ti is not None and len(VT) else [0, 0])
                    nor.append(VN[ni] if ni is not None else flat)
                idx.append(cache[key])
    return np.array(pos, np.float32), np.array(uv, np.float32), np.array(nor, np.float32), np.array(idx, np.uint32)


def convert(obj_path, scale=1.0, up_axis="y"):
    V, VT, VN, groups, mtllib = parse_obj(obj_path)
    base = os.path.dirname(os.path.abspath(obj_path))
    mats = parse_mtl(os.path.join(base, mtllib)) if mtllib else {}
    if up_axis == "z":
        rot = lambda a: np.stack([a[:, 0], a[:, 2], -a[:, 1]], 1) if len(a) else a
        V, VN = rot(V), rot(VN)
    V = V * scale
    chunks, views, accs, prims, materials, images, textures = [], [], [], [], [], [], []
    mat_index, img_index = {}, {}

    def add_view(data, target=None):
        pad = -sum(len(c) for c in chunks) % 4
        if pad: chunks.append(b"\0" * pad)
        off = sum(len(c) for c in chunks); chunks.append(data)
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target: v["target"] = target
        views.append(v); return len(views) - 1

    def add_acc(arr, ctype, typ, target, minmax=False):
        vi = add_view(arr.tobytes(), target)
        a = {"bufferView": vi, "componentType": ctype, "count": len(arr), "type": typ}
        if minmax:
            if len(arr) == 0:
                raise GstInputError("OBJ has no vertices")
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        accs.append(a); return len(accs) - 1

    def material(name):
        if name in mat_index: return mat_index[name]
        m = mats.get(name)
        if m is None: return None
        pbr = {"metallicFactor": 0.0, "roughnessFactor": 1.0}
        if "kd" in m: pbr["baseColorFactor"] = m["kd"] + [m.get("d", 1.0)]
        tex = m.get("map_kd")
        if tex:
            tp = os.path.join(base, tex)
            if os.path.exists(tp):
                if tp not in img_index:
                    from PIL import Image
                    buf = io.BytesIO(); Image.open(tp).convert("RGBA").save(buf, "PNG")
                    images.append({"bufferView": add_view(buf.getvalue()), "mimeType": "image/png", "name": os.path.basename(tex)})
                    textures.append({"source": len(images) - 1}); img_index[tp] = len(textures) - 1
                pbr["baseColorTexture"] = {"index": img_index[tp]}
        mm = {"name": name, "pbrMetallicRoughness": pbr}
        if m.get("d", 1.0) < 1.0: mm["alphaMode"] = "BLEND"
        materials.append(mm); mat_index[name] = len(materials) - 1
        return mat_index[name]

    for name, faces in groups.items():
        pos, uv, nor, idx = build_prim(V, VT, VN, faces)
        if not len(idx): continue
        attrs = {"POSITION": add_acc(pos, 5126, "VEC3", 34962, True), "NORMAL": add_acc(nor, 5126, "VEC3", 34962),
                 "TEXCOORD_0": add_acc(uv, 5126, "VEC2", 34962)}
        small = len(pos) < 65536
        ii = add_acc(idx.astype("<u2" if small else "<u4"), 5123 if small else 5125, "SCALAR", 34963)
        p = {"attributes": attrs, "indices": ii}
        mi = material(name)
        if mi is not None: p["material"] = mi
        prims.append(p)
    if not prims: raise SystemExit("no faces found")
    gltf = {"asset": {"version": "2.0", "generator": "gamestudio-tools obj-to-glb"}, "scene": 0, "scenes": [{"nodes": [0]}],
            "nodes": [{"mesh": 0, "name": os.path.splitext(os.path.basename(obj_path))[0]}],
            "meshes": [{"primitives": prims}], "accessors": accs, "bufferViews": views}
    if materials: gltf["materials"] = materials
    if images: gltf["images"], gltf["textures"] = images, textures
    return gltf, b"".join(chunks)


def write_glb(path, gltf, bin_):
    bin_ += b"\0" * (-len(bin_) % 4)
    gltf["buffers"] = [{"byteLength": len(bin_)}]
    js = json.dumps(gltf, separators=(",", ":")).encode(); js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\x00") + bin_)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert OBJ/MTL to GLB.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--up-axis", choices=["y", "z"], default="y")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    for f in a.inputs:
        g, b = convert(f, a.scale, a.up_axis)
        out = os.path.join(a.outdir, os.path.splitext(os.path.basename(f))[0] + ".glb")
        if os.path.abspath(out) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
        write_glb(out, g, b)
        print(f"{f} -> {out}: {len(g['meshes'][0]['primitives'])} primitive(s), {len(g.get('materials', []))} material(s), {os.path.getsize(out)} B")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
