#!/usr/bin/env python3
"""level-budget: sum objects (and optional tile ids) in Tiled JSON maps against a budget, and flag maps that go over.
Budget JSON:
  {"count": "type",            # how to key objects: "type" (or "class"), "name", or a custom property name
   "defaults": {"enemy": 12, "pickup": 20, "light": 8},
   "maps": {"boss.json": {"enemy": 5}},          # per-map overrides (matched on the file name, then on a glob)
   "ignore": ["spawn", "camera"],
   "tiles": {"hazard": [40, 41]}                 # optional: count cells whose gid (flags stripped) is in the list, as that key
  }
Missing keys in a map are treated as 0. A budget of 0 means "this must not appear". Maps not listed use defaults only.
Text, Markdown and JSON; --fail-on-over (default) and --fail-on-under (maps that have none of a required key with budget > 0).
Finite and infinite maps; encoded (base64 zlib/gzip or csv) tile data is decoded. Group layers are flattened.
"""
import argparse, os, fnmatch, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tilemap-stats"))
import map_diff, tilemap_stats  # noqa: E402

MASK = tilemap_stats.MASK


def key_of(o, mode):
    if mode == "type": return o.get("type") or o.get("class") or ""
    if mode == "name": return o.get("name") or ""
    return str(map_diff.props(o).get(mode, ""))


def counts(m, mode, tiles):
    c = {}
    for _, l in map_diff.flat_layers(m.get("layers", [])):
        if l.get("type") == "objectgroup":
            for o in l.get("objects", []):
                k = key_of(o, mode)
                if k: c[k] = c.get(k, 0) + 1
        elif l.get("type") == "tilelayer" and tiles:
            for g in tilemap_stats.gids_of(l):
                gid = g & MASK
                for k, ids in tiles.items():
                    if gid in ids: c[k] = c.get(k, 0) + 1
    return c


def budget_for(name, cfg):
    b = dict(cfg.get("defaults") or {})
    for pat, ov in (cfg.get("maps") or {}).items():
        if pat == name or fnmatch.fnmatch(name, pat): b.update(ov)
    return b


def check(path, m, cfg):
    name = os.path.basename(path); mode = cfg.get("count") or "type"
    ignore = {s.lower() for s in (cfg.get("ignore") or [])}
    tiles = {k: set(v) for k, v in (cfg.get("tiles") or {}).items()}
    got = {k: v for k, v in counts(m, mode, tiles).items() if k.lower() not in ignore}
    bud = budget_for(name, cfg)
    rows = []
    for k in sorted(set(got) | set(bud)):
        g, b = got.get(k, 0), bud.get(k)
        status = "ok" if b is None or g <= b else "over"
        if b is not None and b > 0 and g == 0: status = "under" if status == "ok" else status
        rows.append({"key": k, "count": g, "budget": b, "status": status})
    return {"file": name, "counts": got, "rows": rows, "over": [r for r in rows if r["status"] == "over"], "under": [r for r in rows if r["status"] == "under"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check Tiled maps against an object budget.")
    ap.add_argument("maps", nargs="+"); ap.add_argument("--budget", required=True); ap.add_argument("--md"); ap.add_argument("--json")
    ap.add_argument("--no-fail-on-over", action="store_true"); ap.add_argument("--fail-on-under", action="store_true")
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
    _src_keys = ('maps',)
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

    cfg = json.load(open(a.budget)); reports = [check(p, json.load(open(p)), cfg) for p in a.maps]
    for r in reports:
        print(f"{r['file']}: " + (", ".join(f"{x['key']} {x['count']}" + (f"/{x['budget']}" if x["budget"] is not None else "") for x in r["rows"]) or "(nothing counted)"))
        for x in r["over"]: print(f"  OVER  {x['key']}: {x['count']} (budget {x['budget']})")
        for x in r["under"]: print(f"  UNDER {x['key']}: {x['count']} (budget {x['budget']})")
    if a.md:
        L = ["# Level budget", "", "| Map | Key | Count | Budget | Status |", "|---|---|---|---|---|"]
        for r in reports:
            for x in r["rows"]: L.append(f"| {r['file']} | {x['key']} | {x['count']} | {x['budget'] if x['budget'] is not None else ''} | {x['status']} |")
        open(a.md, "w").write("\n".join(L) + "\n")
    if a.json: json.dump(reports, open(a.json, "w"), indent=1)
    over, under = sum(len(r["over"]) for r in reports), sum(len(r["under"]) for r in reports)
    print(f"{len(reports)} map(s), {over} over budget, {under} under budget")
    return 1 if (over and not a.no_fail_on_over) or (a.fail_on_under and under) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
