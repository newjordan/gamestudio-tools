#!/usr/bin/env python3
"""asset-unused: report files in an asset folder that no map, atlas, scene, script or glTF references.

Walks `--root` and collects outgoing references from Tiled JSON/TMX/TSX
(image and tileset `source`), atlas-pack JSON (`meta.image`), Godot
`.tscn` / `.tres` / `.gd` and `project.godot` / `.cfg` (`res://` paths:
main scene, icon, autoloads, translations), BMFont `.fnt` page images
(text and XML), and glTF / GLB image and buffer URIs. A file that is only a sidecar of a used file (`.import`,
`.uid`, `.md5`) is not reported. Exit 1 with `--strict` when unused
files remain. Does not delete anything.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402

SKIP_DIRS = {".git", "__pycache__", ".godot", "node_modules"}
SIDECAR_EXTS = {".import", ".uid", ".md5"}
IGNORE_EXTS = {".gd.uid"}  # handled via sidecar
RES_RE = re.compile(r'res://[A-Za-z0-9_./\-]+')
PATH_RE = re.compile(r'path\s*=\s*"(res://[^"]+)"')


def norm(path):
    return os.path.normpath(os.path.abspath(path))


def add(refs, path):
    if path:
        refs.add(norm(path))


def walk_files(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            out.append(os.path.join(dp, fn))
    return out


def maybe_join(base, rel):
    if not rel or rel.startswith("data:"):
        return None
    if os.path.isabs(rel):
        return rel
    return os.path.normpath(os.path.join(base, rel))


def refs_from_json(path, text, refs):
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return
    if not isinstance(doc, dict):
        return
    base = os.path.dirname(path)
    # atlas
    meta = doc.get("meta")
    if isinstance(meta, dict) and meta.get("image"):
        add(refs, maybe_join(base, meta.get("image")))
    # tiled map / tileset
    if "tilewidth" in doc or "tilesets" in doc or doc.get("type") in ("map", "tileset"):
        if doc.get("image"):
            add(refs, maybe_join(base, doc.get("image")))
        for ts in doc.get("tilesets") or []:
            if not isinstance(ts, dict):
                continue
            if ts.get("source"):
                add(refs, maybe_join(base, ts["source"]))
            if ts.get("image"):
                add(refs, maybe_join(base, ts["image"]))
        def walk_layers(layers):
            for l in layers or []:
                if not isinstance(l, dict):
                    continue
                if l.get("image"):
                    add(refs, maybe_join(base, l["image"]))
                walk_layers(l.get("layers") or [])
        walk_layers(doc.get("layers") or [])
    # gltf
    if "asset" in doc and ("buffers" in doc or "images" in doc or "meshes" in doc):
        for key in ("buffers", "images"):
            for item in doc.get(key) or []:
                if isinstance(item, dict) and item.get("uri"):
                    add(refs, maybe_join(base, item["uri"]))


def refs_from_xml(path, refs):
    try:
        root = gst_read.parse_xml(path, "XML").getroot()
    except GstInputError:
        return
    base = os.path.dirname(path)
    for el in root.iter():
        src = el.get("source") or el.get("image")
        if src:
            add(refs, maybe_join(base, src))
        im = el.find("image")
        if im is not None and im.get("source"):
            add(refs, maybe_join(base, im.get("source")))


def refs_from_godot(path, text, refs, project):
    for res in set(PATH_RE.findall(text)) | set(RES_RE.findall(text)):
        rel = res[6:] if res.startswith("res://") else res
        add(refs, os.path.join(project, rel.lstrip("/")))


FNT_PAGE_RE = re.compile(r'^page\b.*?\bfile="?([^"\r\n]+?)"?\s*$', re.M)


def refs_from_fnt(path, text, refs):
    """BMFont page images: text format `page id=0 file="font.png"`, or XML `<page file="..."/>`."""
    base = os.path.dirname(path)
    if text.lstrip().startswith("<"):
        refs_from_xml(path, refs)
        try:
            root = gst_read.parse_xml(path, "XML").getroot()
        except GstInputError:
            return
        for el in root.iter("page"):
            add(refs, maybe_join(base, el.get("file")))
        return
    for f in FNT_PAGE_RE.findall(text):
        add(refs, maybe_join(base, f.strip()))


def collect_refs(files, root, project):
    refs = set()
    # a file always "references" itself when it is a source of refs
    for path in files:
        low = path.lower()
        ext = os.path.splitext(low)[1]
        try:
            if ext in {".json", ".tmj", ".tsj", ".gltf"}:
                text = gst_read.open_text(path, errors="replace")
                refs_from_json(path, text, refs)
                add(refs, path)
            elif ext in {".tmx", ".tsx", ".xml"}:
                refs_from_xml(path, refs)
                add(refs, path)
            elif ext in {".tscn", ".tres", ".gd", ".shader", ".gdshader", ".godot", ".cfg"}:
                text = gst_read.open_text(path, errors="replace")
                refs_from_godot(path, text, refs, project)
                add(refs, path)
            elif ext == ".fnt":
                with open(path, "rb") as fh:
                    head = fh.read(3)
                if head != b"BMF":  # binary BMFont pages are not parsed
                    refs_from_fnt(path, gst_read.open_text(path, errors="replace"), refs)
                add(refs, path)
            elif ext == ".glb":
                add(refs, path)
        except GstInputError:
            # unreadable source: don't crash the inventory; skip its refs
            continue
    return refs


def is_sidecar(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in SIDECAR_EXTS


def main(argv=None):
    ap = argparse.ArgumentParser(description="List asset files that nothing in the folder references.")
    ap.add_argument("root")
    ap.add_argument("--project", help="Godot project root for res:// (default: --root)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when unused files are found")
    ap.add_argument("--include-sidecars", action="store_true", help="also report orphan .import/.uid files")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check(a.root, a.json, a.in_place)
    if not os.path.isdir(a.root):
        raise GstInputError("not a directory: %s" % a.root)
    root = os.path.abspath(a.root)
    project = os.path.abspath(a.project or root)
    files = walk_files(root)
    if not files:
        raise GstInputError("no files under %s" % root)
    refs = collect_refs(files, root, project)
    unused = []
    for path in files:
        apath = norm(path)
        if apath in refs:
            continue
        if is_sidecar(path) and not a.include_sidecars:
            # sidecar of a used file is fine; sidecar of an unused file is ignored too
            # (the unused payload will already be listed, or the payload is used)
            stem = path
            # foo.png.import -> foo.png
            if path.endswith(".import") or path.endswith(".uid") or path.endswith(".md5"):
                stem = path.rsplit(".", 1)[0]
            if norm(stem) in refs or not os.path.exists(stem):
                continue
            # orphan sidecar of a missing/unused payload: skip unless asked
            continue
        unused.append(os.path.relpath(path, root))
    unused.sort()
    for u in unused:
        print("UNUSED  %s" % u)
    print("%d file(s) scanned, %d referenced, %d unused" % (len(files), len(refs), len(unused)))
    rec = {"root": root, "files": len(files), "referenced": len(refs), "unused": unused}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 1 if (a.strict and unused) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
