#!/usr/bin/env python3
"""material-audit: walk a folder (or list) of GLB/glTF files and report unique materials, textures, and missing image URIs.
Per file: material names and PBR factors, texture slots (baseColor, metal-rough, normal, occlusion, emissive, plus
common KHR extras), and whether each image is embedded (bufferView / data URI) or an external file that exists.
A missing external URI or a texture index that points nowhere is flagged. Text, JSON and CSV; --fail-on-missing for CI.
"""
import argparse, os, csv, json, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gltf-inspect"))
import gltf_inspect  # noqa: E402

SLOTS = (
    ("pbrMetallicRoughness", "baseColorTexture"),
    ("pbrMetallicRoughness", "metallicRoughnessTexture"),
    (None, "normalTexture"),
    (None, "occlusionTexture"),
    (None, "emissiveTexture"),
)
KHR_SLOTS = {
    "KHR_materials_pbrSpecularGlossiness": ("diffuseTexture", "specularGlossinessTexture"),
    "KHR_materials_specular": ("specularTexture", "specularColorTexture"),
    "KHR_materials_clearcoat": ("clearcoatTexture", "clearcoatRoughnessTexture", "clearcoatNormalTexture"),
    "KHR_materials_transmission": ("transmissionTexture",),
    "KHR_materials_volume": ("thicknessTexture",),
    "KHR_materials_sheen": ("sheenColorTexture", "sheenRoughnessTexture"),
    "KHR_materials_iridescence": ("iridescenceTexture", "iridescenceThicknessTexture"),
}


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith((".glb", ".gltf")): out.append(os.path.join(root, f))
        elif p.lower().endswith((".glb", ".gltf")):
            out.append(p)
        else:
            raise SystemExit(f"not a GLB/glTF or folder: {p}")
    return sorted(out)


def tex_index(obj):
    if obj is None: return None
    if isinstance(obj, int): return obj
    return obj.get("index")


def image_info(gltf, img, base):
    if img is None: return {"kind": "missing", "uri": None, "ok": False}
    if "bufferView" in img: return {"kind": "embedded", "uri": None, "ok": True, "name": img.get("name")}
    uri = img.get("uri")
    if not uri: return {"kind": "empty", "uri": None, "ok": False, "name": img.get("name")}
    if uri.startswith("data:"): return {"kind": "data", "uri": "data:", "ok": True, "name": img.get("name")}
    path = uri if os.path.isabs(uri) else os.path.join(base, uri)
    return {"kind": "external", "uri": uri, "ok": os.path.isfile(path), "name": img.get("name"), "path": path}


def material_report(path):
    gltf, _bin = gltf_inspect.load(path)
    base = os.path.dirname(os.path.abspath(path))
    images = gltf.get("images") or []
    textures = gltf.get("textures") or []
    mats = []
    missing = []
    def resolve_tex(tex_i, slot, mat_name):
        if tex_i is None: return None
        if not (0 <= tex_i < len(textures)):
            missing.append({"file": path, "material": mat_name, "slot": slot, "reason": f"texture index {tex_i} out of range"})
            return {"slot": slot, "ok": False}
        src = textures[tex_i].get("source")
        if src is None or not (0 <= src < len(images)):
            missing.append({"file": path, "material": mat_name, "slot": slot, "reason": f"image source {src!r} missing"})
            return {"slot": slot, "texture": tex_i, "ok": False}
        info = image_info(gltf, images[src], base)
        rec = {"slot": slot, "texture": tex_i, "image": src, **info}
        if not info["ok"]:
            missing.append({"file": path, "material": mat_name, "slot": slot, "reason": f"missing uri {info.get('uri')}"})
        return rec
    for i, m in enumerate(gltf.get("materials") or []):
        name = m.get("name") or f"material_{i}"
        pbr = m.get("pbrMetallicRoughness") or {}
        rec = {"name": name, "index": i, "baseColorFactor": pbr.get("baseColorFactor"),
               "metallicFactor": pbr.get("metallicFactor"), "roughnessFactor": pbr.get("roughnessFactor"),
               "emissiveFactor": m.get("emissiveFactor"), "alphaMode": m.get("alphaMode"),
               "doubleSided": m.get("doubleSided"), "textures": [], "extensions": list((m.get("extensions") or {}).keys())}
        for group, slot in SLOTS:
            src = (pbr if group else m).get(slot)
            t = resolve_tex(tex_index(src), slot, name)
            if t: rec["textures"].append(t)
        for ext, slots in KHR_SLOTS.items():
            block = (m.get("extensions") or {}).get(ext) or {}
            for slot in slots:
                t = resolve_tex(tex_index(block.get(slot)), f"{ext}.{slot}", name)
                if t: rec["textures"].append(t)
        mats.append(rec)
    # images referenced by no material still counted
    used_images = {t["image"] for rec in mats for t in rec["textures"] if "image" in t}
    orphans = []
    for i, img in enumerate(images):
        info = image_info(gltf, img, base)
        if not info["ok"]:
            missing.append({"file": path, "material": "", "slot": f"image_{i}", "reason": f"missing uri {info.get('uri')}"})
        if i not in used_images: orphans.append({"index": i, **info})
    return {"file": path, "materials": mats, "images": len(images), "textures": len(textures),
            "missing": missing, "orphan_images": orphans}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audit materials and textures across GLB/glTF files.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--fail-on-missing", action="store_true")
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
    _src_keys = ('inputs',)
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

    files = collect(a.inputs)
    if not files: sys.exit("no GLB/glTF files found")
    reports = [material_report(f) for f in files]
    uniq = defaultdict(lambda: {"count": 0, "files": []})
    for r in reports:
        for m in r["materials"]:
            key = m["name"]
            uniq[key]["count"] += 1; uniq[key]["files"].append(os.path.basename(r["file"]))
        nmiss = len(r["missing"])
        print(f"{r['file']}: {len(r['materials'])} material(s), {r['textures']} texture(s), {r['images']} image(s), {nmiss} missing")
        for m in r["materials"]:
            slots = ", ".join(t["slot"] for t in m["textures"]) or "(no textures)"
            print(f"  {m['name']}: {slots}")
        for miss in r["missing"]:
            print(f"  MISSING {miss['slot']}: {miss['reason']}")
    print(f"{len(reports)} file(s), {len(uniq)} unique material name(s), {sum(len(r['missing']) for r in reports)} missing")
    if a.json: json.dump({"files": reports, "unique_materials": {k: v for k, v in uniq.items()}}, open(a.json, "w"), indent=1)
    if a.csv:
        rows = []
        for r in reports:
            for m in r["materials"]:
                rows.append({"file": r["file"], "material": m["name"], "textures": ";".join(t["slot"] for t in m["textures"]),
                             "missing": ";".join(x["reason"] for x in r["missing"] if x["material"] == m["name"])})
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["file", "material", "textures", "missing"]); w.writeheader(); w.writerows(rows)
    return 1 if a.fail_on_missing and any(r["missing"] for r in reports) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
