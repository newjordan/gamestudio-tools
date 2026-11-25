#!/usr/bin/env python3
"""glb-merge: merge several glTF / GLB files into one scene. Buffers are concatenated and
bufferView / accessor / mesh / material / texture / image / sampler / node / skin / animation
indices are remapped. The default scene's root nodes from each input become children of one
wrapper node named after the file stem. Writes a new GLB; inputs are never overwritten unless
`--in-place`.
"""
import argparse, os, copy, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import safe_out, mesh_pivot_fix  # noqa: E402

ARRAYS = (
    "buffers", "bufferViews", "accessors", "samplers", "images", "textures",
    "materials", "meshes", "cameras", "nodes", "skins", "animations", "scenes",
)


def bin_of(chunks):
    if not chunks:
        return b""
    for t, c in chunks:
        if t == b"BIN\x00":
            return c
    return b""


def bump(obj, key, off):
    if off and key in obj and isinstance(obj[key], int):
        obj[key] = obj[key] + off


def bump_list(obj, key, off):
    if off and key in obj and isinstance(obj[key], list):
        obj[key] = [i + off if isinstance(i, int) else i for i in obj[key]]


def remap_mesh(mesh, acc_off, mat_off):
    for prim in mesh.get("primitives") or []:
        attrs = prim.get("attributes") or {}
        for k, v in list(attrs.items()):
            if isinstance(v, int):
                attrs[k] = v + acc_off
        bump(prim, "indices", acc_off)
        bump(prim, "material", mat_off)
        for tgt in prim.get("targets") or []:
            for k, v in list(tgt.items()):
                if isinstance(v, int):
                    tgt[k] = v + acc_off


def remap_node(n, node_off, mesh_off, skin_off, cam_off):
    bump(n, "mesh", mesh_off)
    bump(n, "skin", skin_off)
    bump(n, "camera", cam_off)
    bump_list(n, "children", node_off)


def remap_skin(sk, acc_off, node_off):
    bump(sk, "inverseBindMatrices", acc_off)
    bump(sk, "skeleton", node_off)
    bump_list(sk, "joints", node_off)


def remap_anim(an, acc_off, node_off):
    for ch in an.get("channels") or []:
        tgt = ch.get("target") or {}
        bump(tgt, "node", node_off)
        ch["target"] = tgt
        bump(ch, "sampler", 0)  # samplers are local to the animation
    for sp in an.get("samplers") or []:
        bump(sp, "input", acc_off)
        bump(sp, "output", acc_off)


def remap_image(im, bv_off):
    bump(im, "bufferView", bv_off)


def remap_texture(tx, samp_off, img_off):
    bump(tx, "sampler", samp_off)
    bump(tx, "source", img_off)


def remap_material(mat, tex_off):
    def texinfo(obj, key):
        info = (obj or {}).get(key)
        if isinstance(info, dict):
            bump(info, "index", tex_off)
    texinfo(mat, "normalTexture")
    texinfo(mat, "occlusionTexture")
    texinfo(mat, "emissiveTexture")
    pbr = mat.get("pbrMetallicRoughness") or {}
    texinfo(pbr, "baseColorTexture")
    texinfo(pbr, "metallicRoughnessTexture")
    texinfo(mat, "baseColorTexture")


def pad4(b):
    return b + (b"\x00" * ((4 - (len(b) % 4)) % 4))


def merge(paths):
    out = {"asset": {"version": "2.0", "generator": "gst glb-merge"},
           "scene": 0, "scenes": [{"nodes": []}],
           **{k: [] for k in ARRAYS if k != "scenes"}}
    out["scenes"] = [{"nodes": []}]
    bin_blob = b""
    offsets = {k: 0 for k in ARRAYS}
    roots_for_wrapper = []  # (name, [node indices in merged doc])

    for path in paths:
        js, chunks, ver = mesh_pivot_fix.read_glb(path)
        js = copy.deepcopy(js)
        raw_bin = bin_of(chunks)
        # if gltf with uri buffers, only support embedded / GLB
        for b in js.get("buffers") or []:
            if b.get("uri") and not b["uri"].startswith("data:"):
                raise SystemExit(f"{path}: external buffer URIs are not merged")
        # single concatenated buffer: rewrite bufferViews to buffer 0 + new byteOffset
        if bin_blob:
            bin_blob = pad4(bin_blob)
        cur_bin_off = len(bin_blob)
        for bv in js.get("bufferViews") or []:
            bv["byteOffset"] = int(bv.get("byteOffset") or 0) + cur_bin_off
            bv["buffer"] = 0
        bin_blob += raw_bin

        off = {k: len(out.get(k) or []) for k in ARRAYS}
        # remap in this document
        for bv in js.get("bufferViews") or []:
            pass  # buffer already 0
        for acc in js.get("accessors") or []:
            bump(acc, "bufferView", off["bufferViews"])
            bump(acc, "sparse", 0)
            if "sparse" in acc and isinstance(acc["sparse"], dict):
                for side in ("indices", "values"):
                    if side in acc["sparse"]:
                        bump(acc["sparse"][side], "bufferView", off["bufferViews"])
        for im in js.get("images") or []:
            remap_image(im, off["bufferViews"])
        for tx in js.get("textures") or []:
            remap_texture(tx, off["samplers"], off["images"])
        for mat in js.get("materials") or []:
            remap_material(mat, off["textures"])
        for mesh in js.get("meshes") or []:
            remap_mesh(mesh, off["accessors"], off["materials"])
        for n in js.get("nodes") or []:
            remap_node(n, off["nodes"], off["meshes"], off["skins"], off["cameras"])
        for sk in js.get("skins") or []:
            remap_skin(sk, off["accessors"], off["nodes"])
        for an in js.get("animations") or []:
            remap_anim(an, off["accessors"], off["nodes"])
        # collect this file's scene roots (already remapped)
        default = js.get("scene", 0)
        scenes = js.get("scenes") or []
        roots = []
        if scenes:
            idx = default if isinstance(default, int) and default < len(scenes) else 0
            roots = [n + off["nodes"] for n in (scenes[idx].get("nodes") or [])]
        name = os.path.splitext(os.path.basename(path))[0]
        roots_for_wrapper.append((name, roots))
        # append arrays except buffers/scenes
        for k in ARRAYS:
            if k in ("buffers", "scenes"):
                continue
            out.setdefault(k, []).extend(js.get(k) or [])

    # wrapper nodes
    wrappers = []
    for name, roots in roots_for_wrapper:
        wrappers.append({"name": name, "children": list(roots)})
    base = len(out.get("nodes") or [])
    out.setdefault("nodes", []).extend(wrappers)
    out["scenes"] = [{"name": "merged", "nodes": [base + i for i in range(len(wrappers))]}]
    out["scene"] = 0
    out["buffers"] = [{"byteLength": len(bin_blob)}]
    # drop empty arrays
    for k in list(out):
        if isinstance(out[k], list) and not out[k] and k not in ("scenes", "nodes"):
            del out[k]
    return out, bin_blob


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge several glTF/GLB files into one scene.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check_any(a.inputs, a.out, a.in_place)
    if a.json:
        safe_out.check_any(a.inputs, a.json, a.in_place)
    if len(a.inputs) < 2:
        sys.exit("pass at least two input files to merge")
    js, blob = merge(a.inputs)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    padded = pad4(blob)
    js["buffers"][0]["byteLength"] = len(padded)
    mesh_pivot_fix.write_glb(a.out, js, [(b"BIN\x00", padded)], 2)
    rec = {"inputs": [os.path.basename(p) for p in a.inputs],
           "nodes": len(js.get("nodes") or []),
           "meshes": len(js.get("meshes") or []),
           "out": a.out}
    print(f"merged {len(a.inputs)} file(s), {rec['meshes']} mesh(es), {rec['nodes']} node(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
