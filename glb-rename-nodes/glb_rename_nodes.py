#!/usr/bin/env python3
"""glb-rename-nodes: batch-rename glTF/GLB nodes, meshes and materials (and optionally animations, scenes, skins,
cameras, images) with a regex and replacement, writing a dry-run report or a new file. Skins and animation channels
address nodes by index, so they stay intact. The input is never overwritten.
"""
import argparse, os, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mesh-pivot-fix"))
import mesh_pivot_fix  # noqa: E402

TARGETS = ("nodes", "meshes", "materials", "animations", "scenes", "skins", "cameras", "images", "accessors")
DEFAULT = ("nodes", "meshes", "materials")


def apply_name(name, pat, repl):
    return pat.sub(repl, name or "")


def rename(js, pat, repl, targets, prefix=""):
    changes = []
    for key in targets:
        arr = js.get(key) or []
        for i, item in enumerate(arr):
            if not isinstance(item, dict): continue
            old = item.get("name", "")
            base = old if old != "" else f"{key}_{i}"
            new = apply_name(base, pat, repl)
            if prefix: new = prefix + new
            if new != old:
                changes.append({"target": key, "index": i, "from": old, "to": new})
                item["name"] = new
    return changes


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regex-rename glTF/GLB nodes, meshes and materials.")
    ap.add_argument("input"); ap.add_argument("-o", "--out")
    ap.add_argument("--pattern", default=".*", help="Python regex matched against the current name")
    ap.add_argument("--repl", default=r"\g<0>", help="replacement (backslash groups allowed)")
    ap.add_argument("--prefix", default="", help="prepended to the name after the regex (empty names get target_index)")
    ap.add_argument("--targets", default="nodes,meshes,materials",
                    help="comma list: " + ",".join(TARGETS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if not a.dry_run and not a.out: sys.exit("pass -o or --dry-run")
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.input):
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in TARGETS]
    if bad: sys.exit("unknown target(s): " + ", ".join(bad))
    try:
        pat = re.compile(a.pattern)
    except re.error as e:
        sys.exit(f"bad --pattern: {e}")
    js, chunks, ver = mesh_pivot_fix.read_glb(a.input)
    # deep-ish copy of JSON for dry-run friendliness: we mutate js then maybe don't write
    changes = rename(js, pat, a.repl, targets, a.prefix)
    rec = {"file": a.input, "pattern": a.pattern, "repl": a.repl, "targets": targets,
           "changed": len(changes), "changes": changes, "dry_run": bool(a.dry_run or not a.out)}
    print(f"{len(changes)} rename(s)" + (f" -> {a.out}" if a.out and not a.dry_run else " (dry-run)"))
    for c in changes[:20]:
        print(f"  {c['target']}[{c['index']}]: {c['from']!r} -> {c['to']!r}")
    if len(changes) > 20: print(f"  ... {len(changes) - 20} more")
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    if a.out and not a.dry_run:
        low = a.out.lower()
        if low.endswith(".glb"):
            mesh_pivot_fix.write_glb(a.out, js, chunks or [], ver or 2)
        else:
            # glTF JSON (bin chunk not rewritten; names only live in JSON)
            json.dump(js, open(a.out, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
