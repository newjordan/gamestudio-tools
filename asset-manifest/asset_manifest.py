#!/usr/bin/env python3
"""asset-manifest: content-hash manifest for an asset folder; diff two manifests for incremental builds,
patch lists and "what changed since the last build"; verify a folder against a manifest.
Entries: sha256, bytes, plus image size / WAV duration when readable. Deterministic (no mtimes) so the
manifest itself is stable and diff-able in git.
  build  dir -o manifest.json [--ignore "*.tmp" ...]
  diff   old.json new.json [--json out.json]     exit 1 if anything differs (CI-friendly with --fail)
  verify manifest.json dir                        exit 1 on missing/modified files
"""
import argparse, os, fnmatch, hashlib, json, sys, wave

DEFAULT_IGNORE = [".git/*", "*.import", "*.tmp", "Thumbs.db", ".DS_Store", "*~"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def info(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga"):
            from PIL import Image
            with Image.open(path) as im:
                return {"w": im.width, "h": im.height}
        if ext == ".wav":
            with wave.open(path) as wf:
                return {"sr": wf.getframerate(), "ch": wf.getnchannels(), "seconds": round(wf.getnframes() / wf.getframerate(), 3)}
    except Exception:
        return {"unreadable": True}
    return {}


def ignored(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p) for p in patterns)


def build(root, ignore=None):
    pats = DEFAULT_IGNORE + list(ignore or [])
    files = {}
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if ignored(rel, pats):
                continue
            files[rel] = {"sha256": sha(p), "bytes": os.path.getsize(p), **info(p)}
    return {"schema": "omnispace.asset-manifest/1", "count": len(files), "total_bytes": sum(v["bytes"] for v in files.values()), "files": files}


def diff(old, new):
    o, n = old["files"], new["files"]
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    changed = sorted(k for k in set(o) & set(n) if o[k]["sha256"] != n[k]["sha256"])
    # renames: same hash, removed here, added there
    by_hash = {o[k]["sha256"]: k for k in removed}
    renamed = [(by_hash[n[k]["sha256"]], k) for k in added if n[k]["sha256"] in by_hash]
    r_old = {a for a, _ in renamed}; r_new = {b for _, b in renamed}
    return {"added": [k for k in added if k not in r_new], "removed": [k for k in removed if k not in r_old],
            "changed": changed, "renamed": renamed,
            "patch_bytes": sum(n[k]["bytes"] for k in changed) + sum(n[k]["bytes"] for k in added if k not in r_new)}


def verify(manifest, root):
    cur = build(root, [])
    d = diff(manifest, cur)
    return {"missing": d["removed"] + [a for a, _ in d["renamed"]], "modified": d["changed"], "extra": d["added"] + [b for _, b in d["renamed"]]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Asset manifest build/diff/verify.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("dir"); b.add_argument("-o", "--out", required=True); b.add_argument("--ignore", action="append", default=[])
    d = sub.add_parser("diff"); d.add_argument("old"); d.add_argument("new"); d.add_argument("--json"); d.add_argument("--fail", action="store_true")
    v = sub.add_parser("verify"); v.add_argument("manifest"); v.add_argument("dir")
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
    _src_keys = ('dir', 'old', 'new', 'manifest')
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

    if a.cmd == "build":
        m = build(a.dir, a.ignore)
        json.dump(m, open(a.out, "w"), indent=1, sort_keys=True)
        print(f"{m['count']} file(s), {m['total_bytes']} bytes -> {a.out}")
        return 0
    if a.cmd == "diff":
        r = diff(json.load(open(a.old)), json.load(open(a.new)))
        print(f"added {len(r['added'])}, removed {len(r['removed'])}, changed {len(r['changed'])}, renamed {len(r['renamed'])}, patch {r['patch_bytes']} bytes")
        for k in ("added", "removed", "changed"):
            for f in r[k]: print(f"  {k[:3].upper()} {f}")
        for x, y in r["renamed"]: print(f"  REN {x} -> {y}")
        if a.json: json.dump(r, open(a.json, "w"), indent=1)
        return 1 if a.fail and any(r[k] for k in ("added", "removed", "changed", "renamed")) else 0
    r = verify(json.load(open(a.manifest)), a.dir)
    for k, files in r.items():
        for f in files: print(f"{k.upper()} {f}")
    print("OK" if not (r["missing"] or r["modified"]) else "MISMATCH")
    return 1 if (r["missing"] or r["modified"]) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
