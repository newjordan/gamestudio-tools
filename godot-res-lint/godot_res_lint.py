#!/usr/bin/env python3
"""godot-res-lint: check Godot 4 `.tscn` / `.tres` / `.gd` files for missing `res://` paths.

Walks a project (or a list of files), collects `path="res://..."` from
ExtResource lines and `res://` strings in scripts, and reports anything
that does not resolve under `--root` (the project folder, default: the
input itself if it is a directory). Sidecar `.uid` files are optional
warnings with `--uid`. Exit 1 when errors are present (or warnings with
`--strict`). Does not rewrite files.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402

PATH_RE = re.compile(r'path\s*=\s*"(res://[^"]+)"')
RES_RE = re.compile(r'res://[A-Za-z0-9_./\-]+')
SKIP_DIRS = {".git", "__pycache__", ".godot"}
SCENE_EXTS = {".tscn", ".tres", ".gd", ".shader", ".gdshader"}


def collect_files(root):
    if os.path.isfile(root):
        return [root]
    if not os.path.isdir(root):
        raise GstInputError("not a file or directory: %s" % root)
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in SCENE_EXTS:
                out.append(os.path.join(dp, fn))
    return sorted(out)


def refs_in(path):
    try:
        text = open(path, encoding="utf-8").read()
    except UnicodeDecodeError as e:
        raise GstInputError("file is not valid UTF-8") from e
    found = set(PATH_RE.findall(text))
    if path.lower().endswith(".gd") or path.lower().endswith("shader"):
        found.update(RES_RE.findall(text))
    else:
        # tscn/tres: also catch preload-style res:// in leftover text
        found.update(RES_RE.findall(text))
    return sorted(found)


def resolve(root, res_path):
    rel = res_path[6:] if res_path.startswith("res://") else res_path
    rel = rel.lstrip("/")
    return os.path.normpath(os.path.join(root, rel))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint Godot scenes and scripts for missing res:// paths.")
    ap.add_argument("root", help="project folder, or a single .tscn/.tres/.gd")
    ap.add_argument("--root", dest="project", help="project root used to resolve res:// (default: the input folder)")
    ap.add_argument("--uid", action="store_true", help="warn when a referenced file has no sidecar .uid")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check(a.root, a.json, a.in_place)
    project = a.project or (a.root if os.path.isdir(a.root) else os.path.dirname(os.path.abspath(a.root)))
    if not os.path.isdir(project):
        raise GstInputError("project root is not a directory: %s" % project)
    files = collect_files(a.root)
    if not files:
        raise GstInputError("no Godot scene, resource or script files under %s" % a.root)
    findings = []
    for f in files:
        for ref in refs_in(f):
            dest = resolve(project, ref)
            rec = {"level": "ok", "file": f, "ref": ref, "resolved": dest}
            if not os.path.exists(dest):
                rec["level"] = "error"
                rec["msg"] = "missing"
                findings.append(rec)
            elif a.uid and not dest.endswith(".uid") and not os.path.exists(dest + ".uid"):
                rec["level"] = "warn"
                rec["msg"] = "no .uid sidecar"
                findings.append(rec)
    errors = [f for f in findings if f["level"] == "error"]
    warns = [f for f in findings if f["level"] == "warn"]
    for f in findings:
        print("%s  %s  %s  %s" % (f["level"].upper(), os.path.relpath(f["file"], project), f["ref"], f.get("msg", "")))
    print("%d file(s) scanned: %d error(s), %d warning(s)" % (len(files), len(errors), len(warns)))
    rec = {"files": len(files), "errors": errors, "warnings": warns, "ok": not errors}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    if errors or (a.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
