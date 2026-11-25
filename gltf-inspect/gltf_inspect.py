#!/usr/bin/env python3
"""gltf-inspect: zero-dependency stats + budget check for .glb/.gltf files.

Reports meshes, primitives, vertex/triangle counts, materials, textures (with embedded image sizes),
animations, skins, nodes, bounds, and flags common problems (missing normals/UVs, >65k verts per
primitive, huge textures, non-indexed geometry). Inspired by glTF-Transform's `inspect` (MIT);
written from the Khronos glTF 2.0 spec.
"""
import argparse, os, base64, io, json, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

COMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load(path):
    js, bin_chunk, _ver, _chunks = gst_read.load_gltf_or_glb(path)
    return js, bin_chunk


def buffer_bytes(gltf, idx, bin_chunk, base_dir):
    b = gltf["buffers"][idx]
    uri = b.get("uri")
    if uri is None:
        return bin_chunk
    if uri.startswith("data:"):
        return base64.b64decode(uri.split(",", 1)[1])
    p = os.path.join(base_dir, uri)
    return open(p, "rb").read() if os.path.exists(p) else None


def image_size(gltf, img, bin_chunk, base_dir):
    try:
        from PIL import Image
    except ImportError:
        return None
    raw = None
    if "bufferView" in img:
        bv = gltf["bufferViews"][img["bufferView"]]
        buf = buffer_bytes(gltf, bv["buffer"], bin_chunk, base_dir)
        if buf is not None:
            o = bv.get("byteOffset", 0)
            raw = buf[o:o + bv["byteLength"]]
    elif img.get("uri", "").startswith("data:"):
        raw = base64.b64decode(img["uri"].split(",", 1)[1])
    elif "uri" in img and os.path.exists(os.path.join(base_dir, img["uri"])):
        raw = open(os.path.join(base_dir, img["uri"]), "rb").read()
    if raw is None:
        return None
    try:
        with Image.open(io.BytesIO(raw)) as im:
            return im.size
    except Exception:
        return None


def inspect(path, max_tris=None, max_tex=None):
    gltf, bin_chunk = load(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    acc = gltf.get("accessors", [])
    rep = {"file": os.path.basename(path), "bytes": os.path.getsize(path),
           "generator": gltf.get("asset", {}).get("generator"), "nodes": len(gltf.get("nodes", [])),
           "meshes": [], "materials": [m.get("name", f"material_{i}") for i, m in enumerate(gltf.get("materials", []))],
           "textures": [], "animations": [], "skins": len(gltf.get("skins", [])),
           "extensionsUsed": gltf.get("extensionsUsed", []), "warnings": []}
    tv = tt = 0
    bmin, bmax = [float("inf")] * 3, [float("-inf")] * 3
    for mi, m in enumerate(gltf.get("meshes", [])):
        mrow = {"name": m.get("name", f"mesh_{mi}"), "primitives": []}
        for pi, p in enumerate(m.get("primitives", [])):
            attrs = p.get("attributes", {})
            v = acc[attrs["POSITION"]]["count"] if "POSITION" in attrs else 0
            mode = p.get("mode", 4)
            n_idx = acc[p["indices"]]["count"] if "indices" in p else v
            tris = n_idx // 3 if mode == 4 else max(n_idx - 2, 0) if mode in (5, 6) else 0
            tv += v
            tt += tris
            if "POSITION" in attrs:
                pa = acc[attrs["POSITION"]]
                if "min" in pa and "max" in pa:
                    bmin = [min(a, b) for a, b in zip(bmin, pa["min"])]
                    bmax = [max(a, b) for a, b in zip(bmax, pa["max"])]
            mrow["primitives"].append({"vertices": v, "triangles": tris, "attributes": sorted(attrs), "material": p.get("material")})
            tag = f"{mrow['name']}[{pi}]"
            if "NORMAL" not in attrs:
                rep["warnings"].append(f"{tag}: no NORMAL attribute")
            if "TEXCOORD_0" not in attrs and p.get("material") is not None:
                rep["warnings"].append(f"{tag}: has material but no TEXCOORD_0")
            if "indices" not in p:
                rep["warnings"].append(f"{tag}: non-indexed geometry")
            if v > 65535:
                rep["warnings"].append(f"{tag}: {v} vertices (>65535; needs 32-bit indices / may break mobile)")
        rep["meshes"].append(mrow)
    for ii, img in enumerate(gltf.get("images", [])):
        sz = image_size(gltf, img, bin_chunk, base_dir)
        rep["textures"].append({"name": img.get("name", img.get("uri", f"image_{ii}")), "mime": img.get("mimeType"), "size": sz})
        if sz and max_tex is not None and max(sz) > max_tex:
            rep["warnings"].append(f"image {ii}: {sz[0]}x{sz[1]} exceeds {max_tex}")
    for ai, an in enumerate(gltf.get("animations", [])):
        dur = 0.0
        for s in an.get("samplers", []):
            a = acc[s["input"]]
            if "max" in a:
                dur = max(dur, a["max"][0])
        rep["animations"].append({"name": an.get("name", f"anim_{ai}"), "channels": len(an.get("channels", [])), "seconds": round(dur, 3)})
    rep["totals"] = {"vertices": tv, "triangles": tt}
    if bmin[0] != float("inf"):
        rep["bounds"] = {"min": bmin, "max": bmax, "size": [round(b - a, 4) for a, b in zip(bmin, bmax)]}
    if max_tris is not None and tt > max_tris:
        rep["warnings"].append(f"{tt} triangles exceeds budget {max_tris}")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inspect glTF/GLB files.")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-tris", type=int)
    ap.add_argument("--max-tex", type=int)
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--fail-on-warn", action="store_true")
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
    _src_keys = ('files',)
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

    bad = False
    out = []
    for f in a.files:
        r = inspect(f, a.max_tris, a.max_tex)
        out.append(r)
        bad |= bool(r["warnings"])
        if not a.json:
            print(f"== {r['file']} ({r['bytes']} B, {r['generator']})")
            print(f"   nodes {r['nodes']}  meshes {len(r['meshes'])}  materials {len(r['materials'])}  "
                  f"images {len(r['textures'])}  anims {len(r['animations'])}  skins {r['skins']}")
            print(f"   verts {r['totals']['vertices']}  tris {r['totals']['triangles']}" +
                  (f"  size {r['bounds']['size']}" if "bounds" in r else ""))
            for t in r["textures"]:
                print(f"   tex {t['name']} {t['size']}")
            for an in r["animations"]:
                print(f"   anim {an['name']} {an['seconds']}s ({an['channels']} ch)")
            for w in r["warnings"]:
                print(f"   WARN {w}")
    if a.json:
        print(json.dumps(out, indent=1))
    return 1 if (a.fail_on_warn and bad) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
