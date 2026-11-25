#!/usr/bin/env python3
"""glb-lod: make LOD copies of static .glb meshes with grid vertex clustering.

Cheap and predictable: vertices are snapped to a 3D grid, each cell collapses to one vertex (positions,
normals and other float attributes averaged; UVs taken from the cell's first vertex), degenerate
triangles are dropped. A binary search picks the grid size that lands near the requested triangle ratio.
Supports triangle-list primitives with float attributes and embedded textures. Refuses animated, skinned,
morphed or sparse-accessor files rather than corrupting them. Not a quality simplifier (no edge-collapse
error metric): good for distant LODs, props and collision proxies.
"""
import argparse, os, copy, json, struct, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
DT = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}


def load_glb(path):
    return gst_read.load_glb(path)


def save_glb(path, gltf, bin_):
    bin_ = bin_ + b"\0" * (-len(bin_) % 4)
    gltf["buffers"] = [{"byteLength": len(bin_)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<I4s", len(js), b"JSON") + js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\x00") + bin_)


def read_acc(gltf, bin_, idx):
    try:
        a = gltf["accessors"][idx]
        if "sparse" in a:
            raise SystemExit("sparse accessors are not supported")
        if "bufferView" not in a:
            raise GstInputError("GLB accessor is missing a buffer view")
        bv = gltf["bufferViews"][a["bufferView"]]
        if a["componentType"] not in DT or a["type"] not in NCOMP:
            raise GstInputError("GLB accessor type is unsupported")
        dt = np.dtype("<" + DT[a["componentType"]])
        n = NCOMP[a["type"]]
        stride = bv.get("byteStride") or n * dt.itemsize
        off = int(bv.get("byteOffset", 0) + a.get("byteOffset", 0))
        count = int(a["count"])
        if count < 0 or stride < 1 or off < 0:
            raise GstInputError("GLB accessor is invalid")
        need = off + (count - 1) * stride + n * dt.itemsize if count else off
        if need > len(bin_):
            raise GstInputError("GLB accessor exceeds buffer")
        buf = np.frombuffer(bin_, np.uint8)
        raw = np.lib.stride_tricks.as_strided(buf[off:], shape=(count, n * dt.itemsize), strides=(stride, 1))
        return np.ascontiguousarray(raw).view(dt).reshape(count, n)
    except GstInputError:
        raise
    except SystemExit:
        raise
    except (KeyError, IndexError, ValueError, TypeError, OverflowError) as e:
        raise GstInputError("GLB accessor is invalid: %s" % e) from e


def require_indices(idx, nvert):
    idx = np.asarray(idx).reshape(-1)
    if idx.size % 3 != 0:
        raise GstInputError("GLB index count is not a multiple of 3")
    if idx.size and (int(idx.min()) < 0 or int(idx.max()) >= nvert):
        raise GstInputError("GLB index is out of range")
    return idx


def cluster(pos, cell):
    mn = pos.min(axis=0)
    keys = np.floor((pos - mn) / cell).astype(np.int64)
    uniq, first_idx, inv = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    return inv.reshape(-1), first_idx


def decimate_prim(pos, attrs, idx, ratio):
    target = max(1, int(len(idx) // 3 * ratio))
    diag = float(np.linalg.norm(pos.max(0) - pos.min(0))) or 1.0
    lo, hi = diag / 4096, diag
    best = None
    for _ in range(18):
        mid = (lo * hi) ** 0.5
        inv, first = cluster(pos, mid)
        tri = inv[idx.reshape(-1, 3)]
        ok = (tri[:, 0] != tri[:, 1]) & (tri[:, 1] != tri[:, 2]) & (tri[:, 0] != tri[:, 2])
        n = int(ok.sum())
        best = (inv, first, tri[ok]) if best is None or abs(n - target) < abs(len(best[2]) - target) else best
        if n > target:
            lo = mid
        else:
            hi = mid
    inv, first, tri = best
    m = len(first)
    counts = np.bincount(inv, minlength=m).astype(np.float32)[:, None]
    out = {}
    for name, arr in attrs.items():
        if name.startswith("TEXCOORD"):
            out[name] = arr[first]
        else:
            s = np.zeros((m, arr.shape[1]), np.float64)
            np.add.at(s, inv, arr.astype(np.float64))
            v = (s / counts).astype(np.float32)
            if name == "NORMAL":
                l = np.linalg.norm(v, axis=1, keepdims=True)
                v = v / np.where(l == 0, 1, l)
            out[name] = v.astype(np.float32)
    # compact unused vertices
    used = np.unique(tri)
    remap = np.full(m, -1, np.int64)
    remap[used] = np.arange(len(used))
    out = {k: v[used] for k, v in out.items()}
    return out, remap[tri].reshape(-1)


def simplify(path, ratio, out_path):
    gltf, bin_ = load_glb(path)
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
    before = after = 0
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
                attrs[k] = read_acc(gltf, bin_, ai)
            if "POSITION" not in attrs:
                raise GstInputError("GLB primitive has no POSITION")
            pos = attrs.pop("POSITION").astype(np.float64)
            idx = read_acc(gltf, bin_, p["indices"]).reshape(-1).astype(np.int64) if "indices" in p else np.arange(len(pos))
            idx = require_indices(idx, len(pos))
            before += len(idx) // 3
            if ratio >= 1:
                nattrs, nidx = {k: v.astype(np.float32) for k, v in attrs.items()}, idx
                nattrs["POSITION"] = pos.astype(np.float32)
            else:
                nattrs, nidx = decimate_prim(pos, {"POSITION": pos, **attrs}, idx, ratio)
            after += len(nidx) // 3
            p["attributes"] = {}
            for k, arr in nattrs.items():
                arr = np.ascontiguousarray(arr, dtype="<f4")
                vi = add_view(arr.tobytes(), 34962)
                a = {"bufferView": vi, "componentType": 5126, "count": len(arr), "type": {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}[arr.shape[1]]}
                if k == "POSITION":
                    a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
                accs.append(a)
                p["attributes"][k] = len(accs) - 1
            ct, dt = (5123, "<u2") if len(nattrs["POSITION"]) < 65536 else (5125, "<u4")
            vi = add_view(nidx.astype(dt).tobytes(), 34963)
            accs.append({"bufferView": vi, "componentType": ct, "count": len(nidx), "type": "SCALAR"})
            p["indices"] = len(accs) - 1
    new["bufferViews"], new["accessors"] = views, accs
    save_glb(out_path, new, b"".join(chunks))
    return before, after


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make LOD copies of a static GLB.")
    ap.add_argument("input")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--ratios", default="0.5,0.25,0.1", help="triangle ratios, one LOD file each")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('input',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.input))[0]
    for i, r in enumerate(float(x) for x in a.ratios.split(",")):
        out = os.path.join(a.outdir, f"{base}_lod{i + 1}.glb")
        b, af = simplify(a.input, r, out)
        print(f"{out}: {b} -> {af} tris ({af / max(b, 1):.0%}), {os.path.getsize(out)} B")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
