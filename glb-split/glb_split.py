#!/usr/bin/env python3
"""glb-split: split a multi-root or multi-mesh GLB/glTF into one file per top-level scene
node (default) or per mesh. Each output is pruned with the same reachability pass as
gltf-strip so unused accessors, images and animations are dropped. Animations that
target only nodes in the extracted subtree are kept; channels that point outside are
removed. Writes new files into an output directory; inputs are never overwritten unless
`--in-place`.
"""
import argparse, os, copy, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gltf-strip"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "glb-merge"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import safe_out, gltf_strip, glb_merge, mesh_pivot_fix  # noqa: E402

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb":
        js, chunks, ver = mesh_pivot_fix.read_glb(path)
        return js, glb_merge.bin_of(chunks), ver or 2
    if ext in (".gltf", ".json"):
        js = json.load(open(path, encoding="utf-8"))
        # only buffer-0 with no uri (embedded) or missing bin is supported
        buf = (js.get("buffers") or [{}])[0] if js.get("buffers") else {}
        if buf.get("uri") and not str(buf.get("uri")).startswith("data:"):
            raise SystemExit("external (non-data-URI) buffers are refused; convert to GLB first")
        return js, b"", 2
    raise SystemExit(f"unsupported input: {path}")


def sanitize(name, fallback):
    s = SAFE.sub("_", (name or "").strip()).strip("._")
    return s or fallback


def unique_path(outdir, stem, used):
    base = stem
    n = 2
    while stem.lower() in used:
        stem = f"{base}_{n}"
        n += 1
    used.add(stem.lower())
    return os.path.join(outdir, stem + ".glb"), stem


def filter_animations(js, keep_nodes):
    anims = js.get("animations") or []
    kept = []
    for anim in anims:
        chans = []
        for ch in anim.get("channels") or []:
            t = (ch.get("target") or {}).get("node")
            if t is None or t in keep_nodes:
                chans.append(ch)
        if chans:
            a = dict(anim)
            a["channels"] = chans
            kept.append(a)
    if kept:
        js["animations"] = kept
    elif "animations" in js:
        del js["animations"]


def extract(js, bin_chunk, roots, keep_anims=True):
    js = copy.deepcopy(js)
    keep_nodes = gltf_strip.walk_nodes(js, roots)
    if keep_anims:
        filter_animations(js, keep_nodes)
    elif "animations" in js:
        del js["animations"]
    name = None
    nodes = js.get("nodes") or []
    if len(roots) == 1 and roots[0] < len(nodes):
        name = nodes[roots[0]].get("name")
    js["scenes"] = [{"nodes": list(roots), **({"name": name} if name else {})}]
    js["scene"] = 0
    return gltf_strip.strip(js, bin_chunk, drop_unused_animations=True)


def scene_roots(js):
    scenes = js.get("scenes") or []
    if not scenes:
        # nodes that are not a child of any other node
        kids = set()
        for n in js.get("nodes") or []:
            kids.update(n.get("children") or [])
        return [i for i in range(len(js.get("nodes") or [])) if i not in kids]
    idx = js.get("scene", 0)
    if not isinstance(idx, int) or idx >= len(scenes):
        idx = 0
    return list(scenes[idx].get("nodes") or [])


def mesh_units(js):
    """Yield (stem, root_node_indices, mesh_index) for each mesh."""
    meshes = js.get("meshes") or []
    nodes = js.get("nodes") or []
    used = set()
    out = []
    for mi, mesh in enumerate(meshes):
        owners = [i for i, n in enumerate(nodes) if n.get("mesh") == mi]
        name = mesh.get("name") or (nodes[owners[0]].get("name") if owners else None) or f"mesh_{mi}"
        if not owners:
            # synthesize a root; caller will attach a temp node
            out.append((name, None, mi))
        else:
            out.append((name, owners, mi))
            used.add(mi)
    return out


def extract_mesh(js, bin_chunk, owners, mesh_index, keep_anims=True):
    js = copy.deepcopy(js)
    if owners is None:
        js.setdefault("nodes", []).append({"mesh": mesh_index, "name": (js.get("meshes") or [{}])[mesh_index].get("name") or f"mesh_{mesh_index}"})
        roots = [len(js["nodes"]) - 1]
    else:
        # each owner becomes a root; drop children that do not belong to this mesh's
        # exclusive subtree (children kept only when they don't reference another mesh).
        roots = list(owners)
        for i in roots:
            kids = []
            for c in (js["nodes"][i].get("children") or []):
                kn = js["nodes"][c]
                if kn.get("mesh") in (None, mesh_index):
                    kids.append(c)
            js["nodes"][i] = dict(js["nodes"][i])
            if kids:
                js["nodes"][i]["children"] = kids
            else:
                js["nodes"][i].pop("children", None)
    return extract(js, bin_chunk, roots, keep_anims=keep_anims)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a GLB/glTF into one file per top-level node or mesh.")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True, help="output directory")
    ap.add_argument("--by", choices=("node", "mesh"), default="node",
                    help="split by default-scene roots (node, default) or by mesh")
    ap.add_argument("--no-anims", action="store_true", help="drop animations from every output")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    js, bin_chunk, ver = load(a.input)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)
    os.makedirs(a.out, exist_ok=True)
    written = []
    used_names = set()
    keep_anims = not a.no_anims
    if a.by == "node":
        roots = scene_roots(js)
        if not roots:
            raise SystemExit("no scene roots to split")
        nodes = js.get("nodes") or []
        for i, root in enumerate(roots):
            sub_js, sub_bin = extract(js, bin_chunk, [root], keep_anims=keep_anims)
            raw = nodes[root].get("name") if root < len(nodes) else None
            stem = sanitize(raw, f"node_{i}")
            path, stem = unique_path(a.out, stem, used_names)
            safe_out.check(a.input, path, a.in_place)
            gltf_strip.write(path, sub_js, sub_bin, ver=ver)
            written.append({"name": stem, "path": path, "root": root, "nodes": len(sub_js.get("nodes") or []),
                            "meshes": len(sub_js.get("meshes") or [])})
    else:
        units = mesh_units(js)
        if not units:
            raise SystemExit("no meshes to split")
        for i, (name, owners, mi) in enumerate(units):
            sub_js, sub_bin = extract_mesh(js, bin_chunk, owners, mi, keep_anims=keep_anims)
            stem = sanitize(name, f"mesh_{i}")
            path, stem = unique_path(a.out, stem, used_names)
            safe_out.check(a.input, path, a.in_place)
            gltf_strip.write(path, sub_js, sub_bin, ver=ver)
            written.append({"name": stem, "path": path, "mesh": mi, "nodes": len(sub_js.get("nodes") or []),
                            "meshes": len(sub_js.get("meshes") or [])})
    rec = {"count": len(written), "by": a.by, "files": written, "out": a.out}
    print(f"{len(written)} file(s) ({a.by}) -> {a.out}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
