#!/usr/bin/env python3
"""glb-uv-transform: scale, offset or flip UV (TEXCOORD_*) accessors in a GLB / glTF.
The transform is `uv * scale + offset`, then optional `--flip-u` / `--flip-v` as `1 - u`
or `1 - v`. Every unique TEXCOORD accessor referenced by a mesh primitive is rewritten
as tightly packed float32 with updated min/max. Sparse accessors and external (non-data-URI)
buffers are refused. Writes a new file; the input is never overwritten unless `--in-place`.
"""
import argparse, os, base64, json, re, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-lod"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-merge"))
import safe_out, mesh_pivot_fix, glb_lod, glb_merge  # noqa: E402

DATA_URI = re.compile(r"^data:.*?;base64,(.*)$", re.I)


def parse_vec2(s, default):
    if s is None:
        return list(default)
    parts = [p.strip() for p in str(s).replace(" ", ",").split(",") if p.strip()]
    if len(parts) == 1:
        v = float(parts[0])
        return [v, v]
    if len(parts) != 2:
        raise SystemExit(f"expected one or two numbers, got {s!r}")
    return [float(parts[0]), float(parts[1])]


def load_asset(path):
    js, chunks, ver = mesh_pivot_fix.read_glb(path)
    if chunks is not None:
        return js, glb_merge.bin_of(chunks), "glb", ver or 2
    buffers = js.get("buffers") or []
    if not buffers:
        return js, b"", "gltf", 2
    if len(buffers) > 1:
        raise SystemExit("multiple buffers are not supported")
    uri = buffers[0].get("uri") or ""
    m = DATA_URI.match(uri)
    if m:
        return js, base64.b64decode(m.group(1)), "gltf", 2
    if uri:
        raise SystemExit("external (non-data-URI) buffers are refused")
    raise SystemExit("glTF buffer has no uri (GLB-style .gltf is not supported)")


def texcoord_indices(js):
    found = []
    for mi, mesh in enumerate(js.get("meshes") or []):
        for pi, prim in enumerate(mesh.get("primitives") or []):
            attrs = prim.get("attributes") or {}
            for name, idx in attrs.items():
                if name.startswith("TEXCOORD"):
                    found.append((mi, pi, name, int(idx)))
    return found


def normalize(arr, component_type, normalized):
    arr = np.asarray(arr)
    if not normalized or component_type == 5126:
        return arr.astype(np.float64)
    limits = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}
    if component_type not in limits:
        raise SystemExit(f"unsupported normalized componentType {component_type}")
    return arr.astype(np.float64) / limits[component_type]


def apply_uv(uv, scale, offset, flip_u, flip_v):
    out = uv.astype(np.float64) * np.array(scale, float) + np.array(offset, float)
    if flip_u:
        out[:, 0] = 1.0 - out[:, 0]
    if flip_v:
        out[:, 1] = 1.0 - out[:, 1]
    return out.astype(np.float32)


def transform(js, bin_, scale, offset, flip_u, flip_v):
    refs = texcoord_indices(js)
    if not refs:
        raise SystemExit("no TEXCOORD accessors found on mesh primitives")
    unique = []
    seen = set()
    for _mi, _pi, _name, idx in refs:
        if idx not in seen:
            unique.append(idx)
            seen.add(idx)
    accessors = list(js.get("accessors") or [])
    views = list(js.get("bufferViews") or [])
    blob = bytearray(bin_)
    rec_accs = []
    for idx in unique:
        acc = accessors[idx]
        if "sparse" in acc:
            raise SystemExit(f"accessor {idx} is sparse (refused)")
        if "bufferView" not in acc:
            raise SystemExit(f"accessor {idx} has no bufferView")
        raw = glb_lod.read_acc({"accessors": accessors, "bufferViews": views}, bytes(blob), idx)
        if raw.shape[1] < 2:
            raise SystemExit(f"accessor {idx} is not VEC2")
        uv = normalize(raw[:, :2], acc.get("componentType", 5126), acc.get("normalized", False))
        out = apply_uv(uv, scale, offset, flip_u, flip_v)
        data = out.astype("<f4").tobytes()
        pad = (-len(blob)) % 4
        blob.extend(b"\x00" * pad)
        off = len(blob)
        blob.extend(data)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": 34962})
        new_acc = {
            "bufferView": len(views) - 1,
            "componentType": 5126,
            "count": int(out.shape[0]),
            "type": "VEC2",
            "min": [float(out[:, 0].min()), float(out[:, 1].min())],
            "max": [float(out[:, 0].max()), float(out[:, 1].max())],
        }
        if "name" in acc:
            new_acc["name"] = acc["name"]
        accessors[idx] = new_acc
        rec_accs.append({"accessor": idx, "count": new_acc["count"]})
    js = dict(js)
    js["accessors"] = accessors
    js["bufferViews"] = views
    js["buffers"] = [{"byteLength": len(blob)}]
    rec = {"accessors": rec_accs, "scale": scale, "offset": offset, "flip_u": flip_u, "flip_v": flip_v}
    return js, bytes(blob), rec


def write_asset(path, js, bin_, kind, ver):
    if path.lower().endswith(".glb") or kind == "glb" and path.lower().endswith(".glb"):
        glb_lod.save_glb(path, js, bin_)
        return
    # write .gltf with a data-URI buffer
    uri = "data:application/octet-stream;base64," + base64.b64encode(bin_).decode("ascii")
    js = dict(js)
    js["buffers"] = [{"byteLength": len(bin_), "uri": uri}]
    json.dump(js, open(path, "w"), indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scale, offset or flip UV accessors in a GLB/glTF.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--scale", default="1,1", help="u,v scale (default 1,1; a single number scales both)")
    ap.add_argument("--offset", default="0,0", help="u,v offset added after scale (default 0,0)")
    ap.add_argument("--flip-u", action="store_true", help="after scale/offset, set u to 1-u")
    ap.add_argument("--flip-v", action="store_true", help="after scale/offset, set v to 1-v")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    scale, offset = parse_vec2(a.scale, (1, 1)), parse_vec2(a.offset, (0, 0))
    if not a.flip_u and not a.flip_v and scale == [1.0, 1.0] and offset == [0.0, 0.0]:
        sys.exit("pass --scale, --offset, --flip-u and/or --flip-v")
    js, bin_, kind, ver = load_asset(a.input)
    js, bin_, rec = transform(js, bin_, scale, offset, a.flip_u, a.flip_v)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    write_asset(a.out, js, bin_, kind if a.out.lower().endswith((".glb", ".gltf")) else kind, ver)
    rec["out"] = a.out
    print(f"{len(rec['accessors'])} TEXCOORD accessor(s) scale={scale} offset={offset}"
          f"{' flip-u' if a.flip_u else ''}{' flip-v' if a.flip_v else ''} -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
