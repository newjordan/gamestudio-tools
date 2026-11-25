#!/usr/bin/env python3
"""gltf-strip: shrink a GLB/glTF by dropping unused data and optional metadata, with a before/after report.
Removes meshes, materials, textures, images, samplers, accessors, bufferViews, cameras, skins and nodes that are not
reachable from the file's scenes (plus skin joints and animation targets, which stay). Then packs the remaining
bufferViews into a compact BIN. Optional: --drop-cameras, --drop-lights (KHR_lights_punctual), --drop-extras,
--drop-names, --drop-unused-animations (animations whose targets are all gone). Does not quantise vertices, transcode
textures or flatten the node tree; use glb-lod for mesh simplification. Reports JSON size, BIN size and which arrays
shrank. Skinned or morph-heavy files should be checked in a viewer after stripping (the tool keeps joints and
animation targets, but custom extensions may hold untracked references).
"""
import argparse, os, copy, json, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gltf-inspect"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import gltf_inspect, mesh_pivot_fix  # noqa: E402

# Known material texture pointer paths (tuple of keys, last is the texture-info object with "index")
MAT_TEX = (("pbrMetallicRoughness", "baseColorTexture"), ("pbrMetallicRoughness", "metallicRoughnessTexture"),
           ("normalTexture",), ("occlusionTexture",), ("emissiveTexture",))


def walk_nodes(js, roots):
    nodes = js.get("nodes") or []; seen = set(); stack = list(roots)
    while stack:
        i = stack.pop()
        if i in seen or i < 0 or i >= len(nodes): continue
        seen.add(i); stack.extend(nodes[i].get("children") or [])
    return seen


def animation_nodes(js):
    out = set()
    for an in js.get("animations") or []:
        for ch in an.get("channels") or []:
            n = ch.get("target", {}).get("node")
            if n is not None: out.add(n)
    return out


def skin_nodes(js):
    out = set()
    for s in js.get("skins") or []:
        out.update(s.get("joints") or [])
        if "skeleton" in s: out.add(s["skeleton"])
    return out


def collect_used(js, drop_cameras=False, drop_lights=False, drop_unused_animations=False):
    scenes = js.get("scenes") or []
    roots = [n for s in scenes for n in s.get("nodes") or []]
    if not scenes and js.get("nodes"): roots = list(range(len(js["nodes"])))
    used_n = walk_nodes(js, roots) | skin_nodes(js) | animation_nodes(js)
    if drop_cameras or drop_lights:
        # keep walking from the same roots after we decide to drop camera/light-only leaves later
        pass
    used_mesh, used_mat, used_cam, used_skin, used_light = set(), set(), set(), set(), set()
    nodes = js.get("nodes") or []
    for i in used_n:
        n = nodes[i]
        if "mesh" in n: used_mesh.add(n["mesh"])
        if "camera" in n and not drop_cameras: used_cam.add(n["camera"])
        if "skin" in n: used_skin.add(n["skin"])
        light = ((n.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("light")
        if light is not None and not drop_lights: used_light.add(light)
    for s in (js.get("skins") or []):
        # skins referenced by dropped nodes are ignored via used_skin
        pass
    used_acc, used_tex, used_img, used_samp = set(), set(), set(), set()
    def add_texinfo(info):
        if not info: return
        used_tex.add(info["index"])
    for i in used_mesh:
        for p in js["meshes"][i].get("primitives") or []:
            if "material" in p: used_mat.add(p["material"])
            for acc in p.get("attributes", {}).values(): used_acc.add(acc)
            if "indices" in p: used_acc.add(p["indices"])
            for t in p.get("targets") or []:
                for acc in t.values(): used_acc.add(acc)
    for i in used_mat:
        m = js["materials"][i]
        for path in MAT_TEX:
            o = m
            for k in path: o = (o or {}).get(k) if isinstance(o, dict) else None
            add_texinfo(o)
        # common material extensions that hold a texture index
        for ext in (m.get("extensions") or {}).values():
            if isinstance(ext, dict):
                for v in ext.values():
                    if isinstance(v, dict) and "index" in v and isinstance(v["index"], int): add_texinfo(v)
    for i in used_tex:
        t = js["textures"][i]
        if "source" in t: used_img.add(t["source"])
        if "sampler" in t: used_samp.add(t["sampler"])
    for i in used_img:
        im = js["images"][i]
        if "bufferView" in im:  # tracked via views later
            pass
    used_anim = set()
    for i, an in enumerate(js.get("animations") or []):
        targets = [ch.get("target", {}).get("node") for ch in an.get("channels") or []]
        if drop_unused_animations and targets and not any(t in used_n for t in targets if t is not None): continue
        used_anim.add(i)
        for s in an.get("samplers") or []:
            if "input" in s: used_acc.add(s["input"])
            if "output" in s: used_acc.add(s["output"])
    for i in used_skin:
        s = js["skins"][i]
        if "inverseBindMatrices" in s: used_acc.add(s["inverseBindMatrices"])
    used_view = set()
    for i in used_acc:
        acc = js["accessors"][i]
        if "bufferView" in acc: used_view.add(acc["bufferView"])
        if "sparse" in acc:
            for k in ("indices", "values"):
                if k in acc["sparse"] and "bufferView" in acc["sparse"][k]: used_view.add(acc["sparse"][k]["bufferView"])
    for i in used_img:
        if "bufferView" in js["images"][i]: used_view.add(js["images"][i]["bufferView"])
    return {"nodes": used_n, "meshes": used_mesh, "materials": used_mat, "textures": used_tex, "images": used_img,
            "samplers": used_samp, "cameras": used_cam, "skins": used_skin, "lights": used_light, "accessors": used_acc,
            "views": used_view, "animations": used_anim}


def compact_array(arr, keep, remap_in=None):
    """Return (new_array, old_to_new) for integer indices in keep. Missing or out-of-range indices are omitted."""
    if not arr: return [], {}
    mapping, new = {}, []
    for i, item in enumerate(arr):
        if i in keep:
            mapping[i] = len(new); new.append(item)
    return new, mapping


def apply_map(obj, key, mapping, drop=True):
    if key in obj and obj[key] in mapping: obj[key] = mapping[obj[key]]
    elif key in obj and drop: del obj[key]


def strip_extras(o):
    if isinstance(o, dict):
        o.pop("extras", None)
        for v in list(o.values()): strip_extras(v)
    elif isinstance(o, list):
        for v in o: strip_extras(v)


def strip_names(o, skip=()):
    if isinstance(o, dict):
        if "name" in o and o is not skip: o.pop("name", None)
        for v in o.values(): strip_names(v, skip)
    elif isinstance(o, list):
        for v in o: strip_names(v, skip)


def drop_light_ext(n):
    ext = n.get("extensions") or {}
    ext.pop("KHR_lights_punctual", None)
    if ext: n["extensions"] = ext
    elif "extensions" in n: del n["extensions"]


def prune_camera_light_leaves(js, used, drop_cameras, drop_lights):
    """Remove camera/light-only leaf nodes after dropping those resources, then drop them from scenes and parents."""
    if not (drop_cameras or drop_lights): return
    nodes = js.get("nodes") or []; changed = True
    while changed:
        changed = False; drop = set()
        for i in list(used["nodes"]):
            n = nodes[i]
            if drop_cameras: n.pop("camera", None)
            if drop_lights: drop_light_ext(n)
            children = [c for c in n.get("children") or [] if c in used["nodes"]]
            useful = "mesh" in n or "skin" in n or children
            if not useful: drop.add(i)
        if drop:
            changed = True
            used["nodes"] -= drop
            for n in nodes:
                if "children" in n: n["children"] = [c for c in n["children"] if c not in drop]
            for s in js.get("scenes") or []:
                s["nodes"] = [c for c in s.get("nodes") or [] if c not in drop]


def remap_all(js, maps):
    """maps: dict of array name -> old-to-new."""
    nm, mm, matm, tm, im, sm, cm, skm, lm, am, vm, anm = (maps.get(k, {}) for k in
        ("nodes", "meshes", "materials", "textures", "images", "samplers", "cameras", "skins", "lights", "accessors", "views", "animations"))
    for s in js.get("scenes") or []:
        s["nodes"] = [nm[i] for i in s.get("nodes") or [] if i in nm]
    for n in js.get("nodes") or []:
        if "children" in n: n["children"] = [nm[i] for i in n["children"] if i in nm]
        apply_map(n, "mesh", mm); apply_map(n, "camera", cm); apply_map(n, "skin", skm)
        ext = (n.get("extensions") or {}).get("KHR_lights_punctual")
        if ext and "light" in ext:
            if ext["light"] in lm: ext["light"] = lm[ext["light"]]
            else:
                drop_light_ext(n)
    for mesh in js.get("meshes") or []:
        for p in mesh.get("primitives") or []:
            apply_map(p, "material", matm); apply_map(p, "indices", am)
            p["attributes"] = {k: am[v] for k, v in p.get("attributes", {}).items() if v in am}
            if "targets" in p: p["targets"] = [{k: am[v] for k, v in t.items() if v in am} for t in p["targets"]]
    for mat in js.get("materials") or []:
        for path in MAT_TEX:
            o = mat
            for k in path[:-1]: o = (o or {}).get(k) if isinstance(o, dict) else None
            info = (o or {}).get(path[-1]) if isinstance(o, dict) else None
            if info and "index" in info:
                if info["index"] in tm: info["index"] = tm[info["index"]]
                else: o.pop(path[-1], None)
        for ext in (mat.get("extensions") or {}).values():
            if isinstance(ext, dict):
                for k, v in list(ext.items()):
                    if isinstance(v, dict) and "index" in v and isinstance(v["index"], int):
                        if v["index"] in tm: v["index"] = tm[v["index"]]
                        else: del ext[k]
    for t in js.get("textures") or []:
        apply_map(t, "source", im); apply_map(t, "sampler", sm)
    for imobj in js.get("images") or []:
        apply_map(imobj, "bufferView", vm)
    for acc in js.get("accessors") or []:
        apply_map(acc, "bufferView", vm)
        if "sparse" in acc:
            for k in ("indices", "values"):
                if k in acc["sparse"]: apply_map(acc["sparse"][k], "bufferView", vm)
    for sk in js.get("skins") or []:
        if "joints" in sk: sk["joints"] = [nm[i] for i in sk["joints"] if i in nm]
        apply_map(sk, "skeleton", nm, drop=True); apply_map(sk, "inverseBindMatrices", am)
    for an in js.get("animations") or []:
        for ch in an.get("channels") or []:
            t = ch.get("target") or {}
            if "node" in t:
                if t["node"] in nm: t["node"] = nm[t["node"]]
                else: t.pop("node", None)
            if "sampler" in ch: pass  # sampler index is local to the animation
        for s in an.get("samplers") or []:
            apply_map(s, "input", am); apply_map(s, "output", am)
    ext = (js.get("extensions") or {}).get("KHR_lights_punctual")
    if ext and "lights" in ext:
        ext["lights"] = [ext["lights"][i] for i in range(len(ext["lights"])) if i in lm]
        if not ext["lights"]:
            js["extensions"].pop("KHR_lights_punctual", None)
            used = js.get("extensionsUsed") or []
            js["extensionsUsed"] = [e for e in used if e != "KHR_lights_punctual"]
            if not js["extensionsUsed"]: js.pop("extensionsUsed", None)
            req = js.get("extensionsRequired") or []
            js["extensionsRequired"] = [e for e in req if e != "KHR_lights_punctual"]
            if not js.get("extensionsRequired"): js.pop("extensionsRequired", None)
            if not js.get("extensions"): js.pop("extensions", None)


def pack_bin(js, bin_chunk):
    """Repack used bufferViews into a single compact BIN. Returns the new bytes (or the original if there is nothing to pack)."""
    views = js.get("bufferViews") or []
    if not views: return bin_chunk or b""
    # gather bytes for each view from its buffer
    def buf_bytes(idx):
        if bin_chunk is not None and (js.get("buffers") or [{}])[idx].get("uri") in (None, ""): return bin_chunk
        # external or data URI: go through gltf_inspect if we had a path; caller passes already-loaded bin of buffer 0
        return bin_chunk or b""
    # We only compact buffer 0 in-memory; other buffers with URIs are left and their views keep their offsets.
    new = bytearray(); only0 = True
    for v in views:
        if v.get("buffer", 0) != 0: only0 = False
    if not only0: return bin_chunk or b""
    src = buf_bytes(0)
    for v in views:
        off, ln = v.get("byteOffset", 0), v["byteLength"]
        align = v.get("byteStride") or 4
        pad = (-len(new)) % (align if align else 4)
        new.extend(b"\x00" * pad)
        v["buffer"] = 0; v["byteOffset"] = len(new)
        new.extend(src[off:off + ln])
        if len(src) < off + ln: raise SystemExit("bufferView points past the end of the BIN")
    # 4-byte pad of the chunk itself is applied by the writer
    js["buffers"] = [{"byteLength": len(new)}]
    return bytes(new)


def counts(js):
    ext_l = len((((js.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("lights") or []))
    return {k: len(js.get(k) or []) for k in ("nodes", "meshes", "materials", "textures", "images", "samplers", "cameras", "skins", "accessors", "bufferViews", "animations")} | {"lights": ext_l}


def strip(js, bin_chunk, drop_cameras=False, drop_lights=False, drop_extras=False, drop_names=False, drop_unused_animations=False):
    js = copy.deepcopy(js)
    n_views_before = len(js.get("bufferViews") or [])
    used = collect_used(js, drop_cameras, drop_lights, drop_unused_animations)
    prune_camera_light_leaves(js, used, drop_cameras, drop_lights)
    arrays = {"nodes": "nodes", "meshes": "meshes", "materials": "materials", "textures": "textures", "images": "images",
              "samplers": "samplers", "cameras": "cameras", "skins": "skins", "accessors": "accessors", "bufferViews": "views",
              "animations": "animations"}
    maps = {}
    for field, ukey in arrays.items():
        new, mp = compact_array(js.get(field) or [], used[ukey])
        maps[{"bufferViews": "views", "animations": "animations"}.get(field, field)] = mp
        if field == "bufferViews": maps["views"] = mp
        if new: js[field] = new
        elif field in js: del js[field]
    lights = (((js.get("extensions") or {}).get("KHR_lights_punctual") or {}).get("lights")) or []
    if lights:
        new, lm = compact_array(lights, used["lights"] if not drop_lights else set())
        maps["lights"] = lm
        js["extensions"]["KHR_lights_punctual"]["lights"] = new
        if not new or drop_lights:
            maps["lights"] = {}
    remap_all(js, maps)
    if len(js.get("bufferViews") or []) < n_views_before:
        new_bin = pack_bin(js, bin_chunk)
    else:
        new_bin = bin_chunk or b""
    if drop_extras: strip_extras(js)
    if drop_names: strip_names(js)
    changed = (len(js.get("bufferViews") or []) < n_views_before) or drop_extras or drop_names or drop_cameras or drop_lights or drop_unused_animations
    if changed: js.setdefault("asset", {})["generator"] = "gst gltf-strip"
    if "scene" in js and js.get("scenes") and js["scene"] >= len(js["scenes"]): js["scene"] = 0
    return js, new_bin


def write(path, js, bin_chunk, src_chunks=None, ver=2):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".gltf":
        if bin_chunk is not None:
            bin_path = os.path.splitext(path)[0] + ".bin"
            open(bin_path, "wb").write(bin_chunk)
            js["buffers"] = [{"byteLength": len(bin_chunk), "uri": os.path.basename(bin_path)}]
        json.dump(js, open(path, "w"), indent=2)
        return
    # GLB: reuse mesh_pivot_fix.write_glb's chunk layout, replacing JSON and BIN
    js_blob = json.dumps(js, separators=(",", ":")).encode("utf-8"); js_blob += b" " * (-len(js_blob) % 4)
    bin_pad = (bin_chunk or b"") + b"\x00" * (-len(bin_chunk or b"") % 4)
    chunks = [(b"JSON", js_blob)]
    if bin_pad: chunks.append((b"BIN\x00", bin_pad))
    total = 12 + sum(8 + len(c) for _, c in chunks)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", ver, total))
        for t, c in chunks: f.write(struct.pack("<I4s", len(c), t) + c)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Strip unused data and optional metadata from a GLB/glTF.")
    ap.add_argument("input"); ap.add_argument("-o", "--out", help="output path (default: <name>_strip.glb/.gltf)")
    ap.add_argument("--drop-cameras", action="store_true"); ap.add_argument("--drop-lights", action="store_true")
    ap.add_argument("--drop-extras", action="store_true"); ap.add_argument("--drop-names", action="store_true")
    ap.add_argument("--drop-unused-animations", action="store_true"); ap.add_argument("--json-report")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    ext = os.path.splitext(a.input)[1].lower()
    if ext not in (".glb", ".gltf"): sys.exit("use .glb or .gltf")
    if ext == ".gltf":
        js, bin_chunk = gltf_inspect.load(a.input); chunks, ver = None, 2
    else:
        js, chunks, ver = mesh_pivot_fix.read_glb(a.input)
        bin_chunk = next((c for t, c in (chunks or []) if t == b"BIN\x00"), b"")
        ver = ver or 2
    before = {"arrays": counts(js), "json_bytes": len(json.dumps(js, separators=(",", ":"))), "bin_bytes": len(bin_chunk or b""), "file_bytes": os.path.getsize(a.input)}
    out_js, out_bin = strip(js, bin_chunk, a.drop_cameras, a.drop_lights, a.drop_extras, a.drop_names, a.drop_unused_animations)
    out = a.out or os.path.splitext(a.input)[0] + "_strip" + os.path.splitext(a.input)[1]
    if os.path.abspath(out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    write(out, out_js, out_bin, chunks, ver)
    after = {"arrays": counts(out_js), "json_bytes": len(json.dumps(out_js, separators=(",", ":"))), "bin_bytes": len(out_bin or b""), "file_bytes": os.path.getsize(out)}
    def fmt(k):
        b, c = before["arrays"][k], after["arrays"][k]
        return f"{k} {b}->{c}" if b != c else None
    changed = [fmt(k) for k in before["arrays"] if fmt(k)]
    print(f"{os.path.basename(a.input)} {before['file_bytes']} B -> {out} {after['file_bytes']} B (JSON {before['json_bytes']}->{after['json_bytes']}, BIN {before['bin_bytes']}->{after['bin_bytes']})")
    if changed: print("  " + ", ".join(changed))
    else: print("  nothing to strip (already compact)")
    if a.json_report: json.dump({"before": before, "after": after}, open(a.json_report, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
