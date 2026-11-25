#!/usr/bin/env python3
"""patch-pack: ship only what changed between two builds of an asset folder.
make:  old manifest (asset-manifest JSON) + new folder -> patch.zip containing patch.json (add / change / remove /
       rename operations and the sha256 every resulting file must have) and the new or changed files.
info:  summarise a patch.
apply: check that the target folder really is the old build (sha256 of every file the patch touches), then
       write the new build into --out (default: in place), and verify every file against the patch's hashes.
       --dry-run checks and reports without writing. Refuses unsafe paths inside the zip. Renames keep the patch small.
"""
import argparse, os, hashlib, json, shutil, sys, zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "asset-manifest"))
import asset_manifest  # noqa: E402


def safe(rel):
    n = os.path.normpath(rel).replace("\\", "/")
    if os.path.isabs(rel) or n.startswith("..") or "/../" in n or rel.startswith("/"): raise SystemExit(f"unsafe path in patch: {rel!r}")
    return n


def sha_file(p):
    return asset_manifest.sha(p)


def make(old_manifest, new_dir, out, ignore=None):
    new = asset_manifest.build(new_dir, ignore); d = asset_manifest.diff(old_manifest, new)
    o, n = old_manifest["files"], new["files"]
    ops = {"add": d["added"], "change": d["changed"], "remove": d["removed"], "rename": [list(r) for r in d["renamed"]]}
    patch = {"schema": "gst.patch-pack/1", "ops": ops, "base": {k: o[k]["sha256"] for k in d["changed"] + d["removed"] + [a for a, _ in d["renamed"]]},
             "result": {k: v["sha256"] for k, v in n.items()}}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("patch.json", json.dumps(patch, indent=1, sort_keys=True))
        for k in d["added"] + d["changed"]: z.write(os.path.join(new_dir, k), "files/" + k)
    return patch, os.path.getsize(out)


def load(path):
    z = zipfile.ZipFile(path); patch = json.loads(z.read("patch.json"))
    for k in list(patch["result"]) + [x for r in patch["ops"]["rename"] for x in r]: safe(k)
    return z, patch


def check_base(patch, root):
    bad = []
    for k, h in patch["base"].items():
        p = os.path.join(root, safe(k))
        if not os.path.exists(p): bad.append((k, "missing"))
        elif sha_file(p) != h: bad.append((k, "differs from the build this patch expects"))
    return bad


def apply(patch_path, root, out=None, dry_run=False, force=False):
    z, patch = load(patch_path); out = out or root; bad = check_base(patch, root)
    if bad and not force: return {"ok": False, "errors": bad, "written": 0}
    if dry_run: return {"ok": True, "errors": bad, "written": 0, "dry_run": True, "ops": {k: len(v) for k, v in patch["ops"].items()}}
    if out != root:
        if os.path.exists(out) and os.listdir(out): raise SystemExit(f"--out {out} is not empty")
        shutil.copytree(root, out, dirs_exist_ok=True)
    ops = patch["ops"]; n = 0
    for src, dst in ops["rename"]:
        os.makedirs(os.path.dirname(os.path.join(out, safe(dst))) or ".", exist_ok=True); shutil.move(os.path.join(out, safe(src)), os.path.join(out, safe(dst))); n += 1
    for k in ops["remove"]:
        p = os.path.join(out, safe(k))
        if os.path.exists(p): os.remove(p); n += 1
    for k in ops["add"] + ops["change"]:
        p = os.path.join(out, safe(k)); os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with z.open("files/" + k) as s, open(p, "wb") as f: shutil.copyfileobj(s, f)
        n += 1
    wrong = [(k, "hash mismatch after apply") for k, h in patch["result"].items() if not os.path.exists(os.path.join(out, k)) or sha_file(os.path.join(out, k)) != h]
    return {"ok": not wrong, "errors": wrong, "written": n}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build and apply asset patches.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make"); m.add_argument("old_manifest"); m.add_argument("new_dir"); m.add_argument("-o", "--out", required=True); m.add_argument("--ignore", action="append", default=[])
    i = sub.add_parser("info"); i.add_argument("patch")
    p = sub.add_parser("apply"); p.add_argument("patch"); p.add_argument("target"); p.add_argument("--out"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--force", action="store_true")
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
    _src_keys = ('patch', 'old_manifest', 'new_dir', 'target')
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

    if a.cmd == "make":
        patch, size = make(json.load(open(a.old_manifest)), a.new_dir, a.out, a.ignore); print(f"{a.out}: {size} bytes; " + ", ".join(f"{k} {len(v)}" for k, v in patch["ops"].items())); return 0
    if a.cmd == "info":
        _, patch = load(a.patch); print(", ".join(f"{k} {len(v)}" for k, v in patch["ops"].items()), f"; {len(patch['result'])} files in the result"); return 0
    r = apply(a.patch, a.target, a.out, a.dry_run, a.force)
    for k, why in r["errors"]: print(f"ERROR {k}: {why}")
    print(("DRY RUN: " if r.get("dry_run") else "") + ("ok" if r["ok"] else "FAILED") + f", {r['written']} change(s) written")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
