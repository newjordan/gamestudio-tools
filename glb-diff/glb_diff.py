#!/usr/bin/env python3
"""glb-diff: compare two versions of a model (.glb/.gltf) for review and CI budgets: triangle and vertex
counts (total and per mesh), materials, textures (size changes), animations, bounds and extensions.
Exit 1 when --max-tri-increase / --max-size-increase (percent) are exceeded. Uses gltf-inspect from this kit.
"""
import argparse, os, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gltf-inspect"))
import gltf_inspect  # noqa: E402


def summarize(path):
    r = gltf_inspect.inspect(path)
    return {"bytes": r["bytes"], "tris": r["totals"]["triangles"], "verts": r["totals"]["vertices"],
            "meshes": {m["name"]: sum(p["triangles"] for p in m["primitives"]) for m in r["meshes"]},
            "materials": sorted(r["materials"]), "textures": {t["name"]: tuple(t["size"]) if t["size"] else None for t in r["textures"]},
            "animations": {a["name"]: a["seconds"] for a in r["animations"]}, "bounds": r.get("bounds", {}).get("size"),
            "extensions": sorted(r["extensionsUsed"]), "warnings": r["warnings"]}


def pct(a, b):
    return (b - a) / a * 100 if a else (0.0 if b == 0 else float("inf"))


def compare(old, new):
    d = {"tris": (old["tris"], new["tris"], pct(old["tris"], new["tris"])), "verts": (old["verts"], new["verts"], pct(old["verts"], new["verts"])),
         "bytes": (old["bytes"], new["bytes"], pct(old["bytes"], new["bytes"]))}
    om, nm = old["meshes"], new["meshes"]
    d["meshes"] = {"added": sorted(set(nm) - set(om)), "removed": sorted(set(om) - set(nm)), "changed": {k: (om[k], nm[k]) for k in om if k in nm and om[k] != nm[k]}}
    d["materials"] = {"added": sorted(set(new["materials"]) - set(old["materials"])), "removed": sorted(set(old["materials"]) - set(new["materials"]))}
    ot, nt = old["textures"], new["textures"]
    d["textures"] = {"added": sorted(set(nt) - set(ot)), "removed": sorted(set(ot) - set(nt)), "resized": {k: (ot[k], nt[k]) for k in ot if k in nt and ot[k] != nt[k]}}
    d["animations"] = {"added": sorted(set(new["animations"]) - set(old["animations"])), "removed": sorted(set(old["animations"]) - set(new["animations"]))}
    d["bounds"] = (old["bounds"], new["bounds"]); d["extensions"] = {"added": sorted(set(new["extensions"]) - set(old["extensions"])), "removed": sorted(set(old["extensions"]) - set(new["extensions"]))}
    d["new_warnings"] = [w for w in new["warnings"] if w not in old["warnings"]]
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff two GLB/glTF files.")
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--json")
    ap.add_argument("--max-tri-increase", type=float); ap.add_argument("--max-size-increase", type=float)
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
    _src_keys = ('old', 'new')
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

    d = compare(summarize(a.old), summarize(a.new))
    for k in ("tris", "verts", "bytes"): print(f"{k}: {d[k][0]} -> {d[k][1]} ({d[k][2]:+.1f}%)")
    for sec in ("meshes", "materials", "textures", "animations", "extensions"):
        for kind, v in d[sec].items():
            if v: print(f"{sec} {kind}: {v}")
    if d["bounds"][0] != d["bounds"][1]: print(f"bounds size: {d['bounds'][0]} -> {d['bounds'][1]}")
    for w in d["new_warnings"]: print("NEW WARNING", w)
    if a.json: json.dump(d, open(a.json, "w"), indent=1, default=list)
    bad = (a.max_tri_increase is not None and d["tris"][2] > a.max_tri_increase) or (a.max_size_increase is not None and d["bytes"][2] > a.max_size_increase)
    if bad: print("FAIL: budget exceeded")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
