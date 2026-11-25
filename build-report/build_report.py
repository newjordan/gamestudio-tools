#!/usr/bin/env python3
"""build-report: one Markdown report for a game assets folder, combining sibling tools in this repo:
asset-lint (rules), asset-manifest (counts/size, optional diff against a previous manifest) and
gltf-inspect (per-GLB triangles/warnings). Exit 1 when lint finds errors (or --strict + warnings), so it
can be the single CI step. Imports the sibling modules by path, so keep the tools folder layout intact.
"""
import argparse, os, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("asset-lint", "asset-manifest", "gltf-inspect"):
    sys.path.insert(0, os.path.join(HERE, "..", d))
import asset_lint, asset_manifest, gltf_inspect  # noqa: E402


def build(root, rules=None, prev=None, max_tris=None, max_tex=None):
    rules_list = json.load(open(rules))["rules"] if rules else asset_lint.DEFAULT_RULES["rules"]
    findings = asset_lint.lint(root, rules_list)
    man = asset_manifest.build(root)
    glbs = [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in sorted(fs) if f.lower().endswith((".glb", ".gltf"))]
    models = []
    for g in sorted(glbs):
        try:
            r = gltf_inspect.inspect(g, max_tris, max_tex); models.append((os.path.relpath(g, root), r))
        except Exception as e:
            models.append((os.path.relpath(g, root), {"error": str(e), "warnings": [], "totals": {"triangles": 0}}))
    d = asset_manifest.diff(json.load(open(prev)), man) if prev else None
    return findings, man, models, d


def render(root, findings, man, models, d, max_files=40):
    errs = [f for f in findings if f["level"] == "error"]; warns = [f for f in findings if f["level"] != "error"]
    kinds = {}
    for p, v in man["files"].items(): kinds[os.path.splitext(p)[1].lower() or "(none)"] = kinds.get(os.path.splitext(p)[1].lower() or "(none)", 0) + v["bytes"]
    L = [f"# Asset build report", "", f"Folder: `{root}`", "",
         f"**{'FAIL' if errs else 'PASS'}**: {len(errs)} error(s), {len(warns)} warning(s) | {man['count']} files, {man['total_bytes'] / 1e6:.2f} MB | {len(models)} model(s)", ""]
    L += ["## Size by type", "", "| Type | MB |", "|---|---|"] + [f"| {k} | {v / 1e6:.2f} |" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])] + [""]
    L += ["## Lint findings", ""]
    L += ["None."] if not findings else ["| Level | File | Message |", "|---|---|---|"] + [f"| {f['level']} | `{f['file']}` | {f['msg']} |" for f in findings[:max_files]]
    if len(findings) > max_files: L.append(f"\n...and {len(findings) - max_files} more.")
    L += ["", "## Models", ""]
    if models:
        L += ["| Model | Tris | Verts | Textures | Warnings |", "|---|---|---|---|---|"]
        for n, r in models:
            L.append(f"| `{n}` | {r['totals']['triangles']} | {r.get('totals', {}).get('vertices', '')} | {len(r.get('textures', []))} | {len(r['warnings']) if 'error' not in r else 'ERROR ' + r['error']} |")
    else:
        L.append("No models.")
    if d is not None:
        L += ["", "## Changes since previous manifest", "", f"Added {len(d['added'])}, removed {len(d['removed'])}, changed {len(d['changed'])}, renamed {len(d['renamed'])}; patch size {d['patch_bytes'] / 1e6:.2f} MB", ""]
        for k in ("added", "removed", "changed"):
            for f in d[k][:max_files]: L.append(f"- {k}: `{f}`")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Markdown build report for an asset folder.")
    ap.add_argument("root"); ap.add_argument("-o", "--out"); ap.add_argument("-r", "--rules")
    ap.add_argument("--prev-manifest"); ap.add_argument("--save-manifest")
    ap.add_argument("--max-tris", type=int); ap.add_argument("--max-tex", type=int); ap.add_argument("--strict", action="store_true")
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
    _src_keys = ('root',)
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

    findings, man, models, d = build(a.root, a.rules, a.prev_manifest, a.max_tris, a.max_tex)
    md = render(a.root, findings, man, models, d)
    (open(a.out, "w").write(md) if a.out else print(md))
    if a.save_manifest: json.dump(man, open(a.save_manifest, "w"), indent=1, sort_keys=True)
    errs = sum(f["level"] == "error" for f in findings)
    warns = len(findings) - errs + sum(len(r["warnings"]) for _, r in models)
    print(f"{'FAIL' if errs else 'PASS'}: {errs} error(s), {warns} warning(s)", file=sys.stderr)
    return 1 if errs or (a.strict and warns) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
